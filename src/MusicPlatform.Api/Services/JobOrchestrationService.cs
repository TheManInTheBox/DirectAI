using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;
using MusicPlatform.Api.Hubs;
using System.Text.Json;

namespace MusicPlatform.Api.Services;

/// <summary>
/// Background service that orchestrates job processing by polling for pending jobs
/// and dispatching them to appropriate workers.
/// </summary>
public class JobOrchestrationService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<JobOrchestrationService> _logger;
    private readonly IConfiguration _configuration;
    private readonly SemaphoreSlim _processingSemaphore;

    public JobOrchestrationService(
        IServiceProvider serviceProvider,
        ILogger<JobOrchestrationService> logger,
        IConfiguration configuration)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _configuration = configuration;
        
        var maxConcurrentJobs = _configuration.GetValue("Orchestration:MaxConcurrentJobs", 5);
        _processingSemaphore = new SemaphoreSlim(maxConcurrentJobs, maxConcurrentJobs);
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Job orchestration service started");

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ProcessPendingJobs(stoppingToken);
                await Task.Delay(TimeSpan.FromSeconds(2), stoppingToken); // Poll every 2 seconds
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in job orchestration loop");
                await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken); // Wait longer on error
            }
        }

        _logger.LogInformation("Job orchestration service stopped");
    }

    private async Task ProcessPendingJobs(CancellationToken cancellationToken)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();
        var jobService = scope.ServiceProvider.GetRequiredService<IdempotentJobService>();

        // Get pending or retrying jobs, ordered by creation time
        var pendingJobs = await dbContext.Jobs
            .Where(j => j.Status == JobStatus.Pending || j.Status == JobStatus.Retrying)
            .OrderBy(j => j.StartedAt)
            .Take(10) // Process up to 10 jobs at a time
            .ToListAsync(cancellationToken);

        if (!pendingJobs.Any())
        {
            return;
        }

        _logger.LogDebug("Found {Count} pending jobs to process", pendingJobs.Count);

        // Process jobs concurrently, respecting semaphore limits
        var processingTasks = pendingJobs.Select(job => ProcessJob(job, cancellationToken));
        await Task.WhenAll(processingTasks);
    }

    private async Task ProcessJob(Job job, CancellationToken cancellationToken)
    {
        await _processingSemaphore.WaitAsync(cancellationToken);
        
        try
        {
            using var scope = _serviceProvider.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();
            var jobService = scope.ServiceProvider.GetRequiredService<IdempotentJobService>();
            var httpClientFactory = scope.ServiceProvider.GetRequiredService<IHttpClientFactory>();

            // Check if job is still pending (might have been picked up by another instance)
            var currentJob = await dbContext.Jobs.FindAsync(job.Id);
            if (currentJob == null || (currentJob.Status != JobStatus.Pending && currentJob.Status != JobStatus.Retrying))
            {
                return;
            }

            _logger.LogInformation("Processing job {JobId} of type {JobType}", job.Id, job.Type);

            // Mark job as running
            var workerInstanceId = Environment.MachineName + "_" + Environment.ProcessId;
            var started = await jobService.StartJobProcessingAsync(job.Id, workerInstanceId);
            if (!started)
            {
                _logger.LogWarning("Could not start processing job {JobId}, skipping", job.Id);
                return;
            }

            // Send real-time progress update
            var progressService = scope.ServiceProvider.GetRequiredService<JobProgressService>();
            await progressService.SendJobProgressUpdate(job.Id, "Running", "initializing", 5, 
                "🚀 Starting comprehensive analysis...");

            // Update checkpoints
            await jobService.UpdateJobWithHeartbeatAsync(job.Id, JobStatus.Running, "initialized", new Dictionary<string, object>
            {
                ["initialized_at"] = DateTime.UtcNow
            });

            // Dispatch to appropriate worker
            switch (job.Type)
            {
                case JobType.Analysis:
                    await ProcessAnalysisJob(job, httpClientFactory, jobService, cancellationToken);
                    break;
                case JobType.Generation:
                    await ProcessGenerationJob(job, httpClientFactory, jobService, cancellationToken);
                    break;
                default:
                    await jobService.FailJobAsync(job.Id, $"Unknown job type: {job.Type}");
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing job {JobId}", job.Id);
            
            using var scope = _serviceProvider.CreateScope();
            var jobService = scope.ServiceProvider.GetRequiredService<IdempotentJobService>();
            await jobService.FailJobAsync(job.Id, $"Processing error: {ex.Message}");
        }
        finally
        {
            _processingSemaphore.Release();
        }
    }

    private async Task ProcessAnalysisJob(Job job, IHttpClientFactory httpClientFactory, 
        IdempotentJobService jobService, CancellationToken cancellationToken)
    {
        // Get progress service for real-time updates
        using var scope = _serviceProvider.CreateScope();
        var progressService = scope.ServiceProvider.GetRequiredService<JobProgressService>();
        
        var httpClient = httpClientFactory.CreateClient("AnalysisWorker");

        // Get API base URL from configuration
        var apiBaseUrl = _configuration.GetValue<string>("ApiBaseUrl") 
            ?? Environment.GetEnvironmentVariable("API_BASE_URL")
            ?? "http://localhost:5000";

        // Prepare analysis request
        var request = new
        {
            audio_file_id = job.EntityId.ToString(),
            blob_uri = job.Metadata.GetValueOrDefault("BlobUri")?.ToString(),
            callback_url = $"{apiBaseUrl}/api/audio/{job.EntityId}/analysis-complete"
        };

        _logger.LogInformation("Sending analysis request for job {JobId} to worker", job.Id);

        // Send real-time progress update
        await progressService.SendJobProgressUpdate(job.Id, "Running", "worker_processing", 15, 
            "🎵 Sending audio to analysis worker...");

        // Send request to analysis worker
        var response = await httpClient.PostAsJsonAsync("/analyze", request, cancellationToken);

        await jobService.UpdateJobWithHeartbeatAsync(job.Id, null, "worker_processing", new Dictionary<string, object>
        {
            ["worker_response_received"] = DateTime.UtcNow,
            ["worker_status_code"] = (int)response.StatusCode
        });

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            await jobService.FailJobAsync(job.Id, $"Worker request failed: {response.StatusCode} - {errorContent}");
            return;
        }

        _logger.LogInformation("Analysis job {JobId} accepted by worker", job.Id);
        // Note: Job completion will be handled by the worker callback
    }

    private async Task ProcessGenerationJob(Job job, IHttpClientFactory httpClientFactory, 
        IdempotentJobService jobService, CancellationToken cancellationToken)
    {
        // Get progress service for real-time updates
        using var scope = _serviceProvider.CreateScope();
        var progressService = scope.ServiceProvider.GetRequiredService<JobProgressService>();
        
        var httpClient = httpClientFactory.CreateClient("GenerationWorker");

        // Get API base URL from configuration
        var apiBaseUrl = _configuration.GetValue<string>("ApiBaseUrl") 
            ?? Environment.GetEnvironmentVariable("API_BASE_URL")
            ?? "http://localhost:5000";

        // Prepare generation request from job metadata
        var request = new
        {
            generation_request_id = job.EntityId.ToString(),
            prompt = job.Metadata.GetValueOrDefault("Prompt")?.ToString(),
            target_stems = job.Metadata.GetValueOrDefault("TargetStems")?.ToString(),
            callback_url = $"{apiBaseUrl}/api/generation/{job.EntityId}/complete"
        };

        _logger.LogInformation("Sending generation request for job {JobId} to worker", job.Id);

        // Send real-time progress update
        await progressService.SendJobProgressUpdate(job.Id, "Running", "worker_processing", 15, 
            "🎶 Sending generation request to worker...");

        // Send request to generation worker
        var response = await httpClient.PostAsJsonAsync("/generate", request, cancellationToken);

        await jobService.UpdateJobWithHeartbeatAsync(job.Id, null, "worker_processing", new Dictionary<string, object>
        {
            ["worker_response_received"] = DateTime.UtcNow,
            ["worker_status_code"] = (int)response.StatusCode
        });

        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            await jobService.FailJobAsync(job.Id, $"Worker request failed: {response.StatusCode} - {errorContent}");
            return;
        }

        _logger.LogInformation("Generation job {JobId} accepted by worker", job.Id);
        // Note: Job completion will be handled by the worker callback
    }

    public override void Dispose()
    {
        _processingSemaphore?.Dispose();
        base.Dispose();
    }
}