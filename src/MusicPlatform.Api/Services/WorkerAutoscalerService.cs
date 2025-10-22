using Microsoft.EntityFrameworkCore;
using MusicPlatform.Infrastructure.Data;
using System.Diagnostics;

namespace MusicPlatform.Api.Services;

/// <summary>
/// Background service that monitors job queue depth and dynamically scales
/// Docker worker containers up/down based on demand.
/// </summary>
public class WorkerAutoscalerService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<WorkerAutoscalerService> _logger;
    private readonly IConfiguration _configuration;
    private readonly bool _enabled;
    private readonly int _minWorkers;
    private readonly int _maxWorkers;
    private readonly int _scaleUpThreshold;
    private readonly int _scaleDownThreshold;
    private readonly TimeSpan _cooldownPeriod;
    private DateTime _lastScaleAction = DateTime.MinValue;
    private int _currentAnalysisWorkers = 1;
    private int _currentGenerationWorkers = 1;

    public WorkerAutoscalerService(
        IServiceProvider serviceProvider,
        ILogger<WorkerAutoscalerService> logger,
        IConfiguration configuration)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _configuration = configuration;

        // Read autoscaling configuration
        _enabled = _configuration.GetValue("Autoscaling:Enabled", false);
        _minWorkers = _configuration.GetValue("Autoscaling:MinWorkers", 1);
        _maxWorkers = _configuration.GetValue("Autoscaling:MaxWorkers", 5);
        _scaleUpThreshold = _configuration.GetValue("Autoscaling:ScaleUpThreshold", 3);
        _scaleDownThreshold = _configuration.GetValue("Autoscaling:ScaleDownThreshold", 1);
        _cooldownPeriod = TimeSpan.FromSeconds(_configuration.GetValue("Autoscaling:CooldownSeconds", 60));

        if (_enabled)
        {
            _logger.LogInformation(
                "Worker autoscaler enabled: Min={Min}, Max={Max}, ScaleUpThreshold={Up}, ScaleDownThreshold={Down}, Cooldown={Cooldown}s",
                _minWorkers, _maxWorkers, _scaleUpThreshold, _scaleDownThreshold, _cooldownPeriod.TotalSeconds);
        }
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_enabled)
        {
            _logger.LogInformation("Worker autoscaler is disabled");
            return;
        }

        _logger.LogInformation("Worker autoscaler started");

        // Check if Docker is available
        if (!IsDockerAvailable())
        {
            _logger.LogWarning("Docker is not available. Autoscaler will be disabled.");
            return;
        }

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await EvaluateAndScaleWorkers(stoppingToken);
                await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken); // Check every 10 seconds
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in worker autoscaler loop");
                await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
            }
        }

        _logger.LogInformation("Worker autoscaler stopped");
    }

    private async Task EvaluateAndScaleWorkers(CancellationToken cancellationToken)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();

        // Get queue depth by job type
        var analysisQueueDepth = await dbContext.Jobs
            .Where(j => j.Type == Domain.Models.JobType.Analysis && 
                       (j.Status == Domain.Models.JobStatus.Pending || 
                        j.Status == Domain.Models.JobStatus.Retrying))
            .CountAsync(cancellationToken);

        var generationQueueDepth = await dbContext.Jobs
            .Where(j => j.Type == Domain.Models.JobType.Generation && 
                       (j.Status == Domain.Models.JobStatus.Pending || 
                        j.Status == Domain.Models.JobStatus.Retrying))
            .CountAsync(cancellationToken);

        var runningAnalysisJobs = await dbContext.Jobs
            .Where(j => j.Type == Domain.Models.JobType.Analysis && 
                       j.Status == Domain.Models.JobStatus.Running)
            .CountAsync(cancellationToken);

        var runningGenerationJobs = await dbContext.Jobs
            .Where(j => j.Type == Domain.Models.JobType.Generation && 
                       j.Status == Domain.Models.JobStatus.Running)
            .CountAsync(cancellationToken);

        _logger.LogDebug(
            "Queue depth - Analysis: {AnalysisQueue} ({AnalysisRunning} running), Generation: {GenerationQueue} ({GenerationRunning} running)",
            analysisQueueDepth, runningAnalysisJobs, generationQueueDepth, runningGenerationJobs);

        // Check cooldown period
        if (DateTime.UtcNow - _lastScaleAction < _cooldownPeriod)
        {
            return;
        }

        // Scale analysis workers
        _currentAnalysisWorkers = await ScaleWorkerType("analysis", analysisQueueDepth, runningAnalysisJobs, 
            _currentAnalysisWorkers, cancellationToken);

        // Scale generation workers
        _currentGenerationWorkers = await ScaleWorkerType("generation", generationQueueDepth, runningGenerationJobs, 
            _currentGenerationWorkers, cancellationToken);
    }

    private async Task<int> ScaleWorkerType(string workerType, int queueDepth, int runningJobs,
        int currentWorkers, CancellationToken cancellationToken)
    {
        int desiredWorkers = currentWorkers;

        // Determine desired worker count based on queue depth and running jobs
        int totalLoad = queueDepth + runningJobs;

        if (totalLoad >= _scaleUpThreshold && currentWorkers < _maxWorkers)
        {
            // Scale up: Add workers proportional to queue depth
            desiredWorkers = Math.Min(_maxWorkers, currentWorkers + (totalLoad / _scaleUpThreshold));
            _logger.LogInformation(
                "Scaling UP {WorkerType} workers: {Current} -> {Desired} (load: {Load})",
                workerType, currentWorkers, desiredWorkers, totalLoad);
        }
        else if (totalLoad <= _scaleDownThreshold && currentWorkers > _minWorkers)
        {
            // Scale down: Remove workers when load is low
            desiredWorkers = Math.Max(_minWorkers, currentWorkers - 1);
            _logger.LogInformation(
                "Scaling DOWN {WorkerType} workers: {Current} -> {Desired} (load: {Load})",
                workerType, currentWorkers, desiredWorkers, totalLoad);
        }

        if (desiredWorkers != currentWorkers)
        {
            bool success = await ScaleDockerWorkers(workerType, desiredWorkers, cancellationToken);
            if (success)
            {
                currentWorkers = desiredWorkers;
                _lastScaleAction = DateTime.UtcNow;
            }
        }
        return currentWorkers;
    }

    private async Task<bool> ScaleDockerWorkers(string workerType, int desiredReplicas, 
        CancellationToken cancellationToken)
    {
        try
        {
            var containerPrefix = workerType == "analysis" ? "music-analysis-worker" : "music-generation-worker";
            
            // Use docker-compose scale command
            var startInfo = new ProcessStartInfo
            {
                FileName = "docker-compose",
                Arguments = $"up -d --scale {workerType}-worker={desiredReplicas} --no-recreate",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = Directory.GetCurrentDirectory()
            };

            _logger.LogInformation("Executing: docker-compose up -d --scale {WorkerType}-worker={Replicas}",
                workerType, desiredReplicas);

            using var process = Process.Start(startInfo);
            if (process == null)
            {
                _logger.LogError("Failed to start docker-compose process");
                return false;
            }

            var output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
            var error = await process.StandardError.ReadToEndAsync(cancellationToken);
            await process.WaitForExitAsync(cancellationToken);

            if (process.ExitCode != 0)
            {
                _logger.LogError("Docker-compose scaling failed: {Error}", error);
                return false;
            }

            _logger.LogInformation("Successfully scaled {WorkerType} workers to {Replicas}", 
                workerType, desiredReplicas);
            
            if (!string.IsNullOrWhiteSpace(output))
            {
                _logger.LogDebug("Docker-compose output: {Output}", output);
            }

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error scaling {WorkerType} workers to {Replicas}", 
                workerType, desiredReplicas);
            return false;
        }
    }

    private bool IsDockerAvailable()
    {
        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "docker",
                Arguments = "--version",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            if (process == null) return false;

            process.WaitForExit(5000);
            return process.ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }
}
