using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Infrastructure.Data;
using MusicPlatform.Domain.Models;

namespace MusicPlatform.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MetricsController : ControllerBase
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly IConfiguration _configuration;
    private readonly ILogger<MetricsController> _logger;

    public MetricsController(
        MusicPlatformDbContext dbContext,
        IConfiguration configuration,
        ILogger<MetricsController> logger)
    {
        _dbContext = dbContext;
        _configuration = configuration;
        _logger = logger;
    }

    /// <summary>
    /// Get autoscaling metrics and current worker status
    /// </summary>
    [HttpGet("autoscaling")]
    public async Task<IActionResult> GetAutoscalingMetrics()
    {
        var enabled = _configuration.GetValue("Autoscaling:Enabled", false);
        var minWorkers = _configuration.GetValue("Autoscaling:MinWorkers", 1);
        var maxWorkers = _configuration.GetValue("Autoscaling:MaxWorkers", 5);
        var scaleUpThreshold = _configuration.GetValue("Autoscaling:ScaleUpThreshold", 3);
        var scaleDownThreshold = _configuration.GetValue("Autoscaling:ScaleDownThreshold", 1);

        // Get job queue metrics
        var analysisQueueDepth = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Analysis && 
                       (j.Status == JobStatus.Pending || j.Status == JobStatus.Retrying))
            .CountAsync();

        var generationQueueDepth = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Generation && 
                       (j.Status == JobStatus.Pending || j.Status == JobStatus.Retrying))
            .CountAsync();

        var analysisRunning = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Running)
            .CountAsync();

        var generationRunning = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Generation && j.Status == JobStatus.Running)
            .CountAsync();

        var analysisCompleted = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Completed)
            .CountAsync();

        var generationCompleted = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Generation && j.Status == JobStatus.Completed)
            .CountAsync();

        var analysisFailed = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Failed)
            .CountAsync();

        var generationFailed = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Generation && j.Status == JobStatus.Failed)
            .CountAsync();

        // Calculate average processing time for completed jobs in last 24 hours
        var since = DateTime.UtcNow.AddDays(-1);
        var completedJobs = await _dbContext.Jobs
            .Where(j => j.Status == JobStatus.Completed && 
                       j.CompletedAt != null && 
                       j.CompletedAt >= since)
            .Select(j => new 
            { 
                j.Type, 
                Duration = EF.Functions.DateDiffSecond(j.StartedAt, j.CompletedAt!.Value)
            })
            .ToListAsync();

        var avgAnalysisTime = completedJobs
            .Where(j => j.Type == JobType.Analysis)
            .Average(j => (double?)j.Duration) ?? 0;

        var avgGenerationTime = completedJobs
            .Where(j => j.Type == JobType.Generation)
            .Average(j => (double?)j.Duration) ?? 0;

        return Ok(new
        {
            autoscaling = new
            {
                enabled,
                minWorkers,
                maxWorkers,
                scaleUpThreshold,
                scaleDownThreshold,
                status = enabled ? "active" : "disabled"
            },
            analysis = new
            {
                queue = new
                {
                    pending = analysisQueueDepth,
                    running = analysisRunning,
                    total = analysisQueueDepth + analysisRunning
                },
                lifetime = new
                {
                    completed = analysisCompleted,
                    failed = analysisFailed,
                    avgProcessingTimeSeconds = Math.Round(avgAnalysisTime, 2)
                },
                metrics = new
                {
                    utilizationPercent = maxWorkers > 0 
                        ? Math.Round((double)analysisRunning / maxWorkers * 100, 2) 
                        : 0,
                    shouldScaleUp = (analysisQueueDepth + analysisRunning) >= scaleUpThreshold,
                    shouldScaleDown = (analysisQueueDepth + analysisRunning) <= scaleDownThreshold
                }
            },
            generation = new
            {
                queue = new
                {
                    pending = generationQueueDepth,
                    running = generationRunning,
                    total = generationQueueDepth + generationRunning
                },
                lifetime = new
                {
                    completed = generationCompleted,
                    failed = generationFailed,
                    avgProcessingTimeSeconds = Math.Round(avgGenerationTime, 2)
                },
                metrics = new
                {
                    utilizationPercent = maxWorkers > 0 
                        ? Math.Round((double)generationRunning / maxWorkers * 100, 2) 
                        : 0,
                    shouldScaleUp = (generationQueueDepth + generationRunning) >= scaleUpThreshold,
                    shouldScaleDown = (generationQueueDepth + generationRunning) <= scaleDownThreshold
                }
            },
            timestamp = DateTime.UtcNow
        });
    }

    /// <summary>
    /// Get job statistics by status
    /// </summary>
    [HttpGet("jobs/stats")]
    public async Task<IActionResult> GetJobStats()
    {
        var stats = await _dbContext.Jobs
            .GroupBy(j => new { j.Type, j.Status })
            .Select(g => new 
            { 
                Type = g.Key.Type.ToString(),
                Status = g.Key.Status.ToString(),
                Count = g.Count()
            })
            .ToListAsync();

        return Ok(new
        {
            statistics = stats,
            timestamp = DateTime.UtcNow
        });
    }

    /// <summary>
    /// Get recent job activity
    /// </summary>
    [HttpGet("jobs/recent")]
    public async Task<IActionResult> GetRecentJobActivity([FromQuery] int hours = 24)
    {
        var since = DateTime.UtcNow.AddHours(-hours);
        
        var recentJobs = await _dbContext.Jobs
            .Where(j => j.StartedAt >= since)
            .OrderByDescending(j => j.StartedAt)
            .Take(50)
            .Select(j => new
            {
                j.Id,
                Type = j.Type.ToString(),
                Status = j.Status.ToString(),
                j.StartedAt,
                j.CompletedAt,
                DurationSeconds = j.CompletedAt != null 
                    ? EF.Functions.DateDiffSecond(j.StartedAt, j.CompletedAt.Value)
                    : (int?)null,
                j.ErrorMessage
            })
            .ToListAsync();

        return Ok(new
        {
            hours,
            count = recentJobs.Count,
            jobs = recentJobs,
            timestamp = DateTime.UtcNow
        });
    }
}
