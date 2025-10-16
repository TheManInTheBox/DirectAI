using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;

namespace MusicPlatform.Api.Controllers;

/// <summary>
/// Controller for job status tracking and orchestration management.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class JobsController : ControllerBase
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly ILogger<JobsController> _logger;

    public JobsController(
        MusicPlatformDbContext dbContext,
        ILogger<JobsController> logger)
    {
        _dbContext = dbContext;
        _logger = logger;
    }

    /// <summary>
    /// Get job status by ID.
    /// </summary>
    /// <param name="id">Job ID</param>
    /// <returns>Job details including status and metadata</returns>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(Job), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<Job>> GetJob(Guid id)
    {
        var job = await _dbContext.Jobs.FindAsync(id);
        
        if (job == null)
            return NotFound($"Job with ID {id} not found");

        return Ok(job);
    }

    /// <summary>
    /// Get all jobs for a specific entity (audio file or generation request).
    /// </summary>
    /// <param name="entityId">Audio file ID or generation request ID</param>
    /// <returns>List of jobs associated with the entity</returns>
    [HttpGet("entity/{entityId}")]
    [ProducesResponseType(typeof(IEnumerable<Job>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<Job>>> GetJobsByEntity(Guid entityId)
    {
        var jobs = await _dbContext.Jobs
            .Where(j => j.EntityId == entityId)
            .OrderByDescending(j => j.StartedAt)
            .ToListAsync();

        return Ok(jobs);
    }

    /// <summary>
    /// Get all jobs (with filtering and pagination).
    /// </summary>
    /// <param name="status">Optional status filter</param>
    /// <param name="type">Optional job type filter</param>
    /// <param name="skip">Number of records to skip</param>
    /// <param name="take">Number of records to take</param>
    /// <returns>List of jobs</returns>
    [HttpGet]
    [ProducesResponseType(typeof(IEnumerable<Job>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<Job>>> GetJobs(
        [FromQuery] JobStatus? status = null,
        [FromQuery] JobType? type = null,
        [FromQuery] int skip = 0,
        [FromQuery] int take = 20)
    {
        if (take > 100) take = 100; // Max 100 records per request

        var query = _dbContext.Jobs.AsQueryable();

        if (status.HasValue)
            query = query.Where(j => j.Status == status.Value);

        if (type.HasValue)
            query = query.Where(j => j.Type == type.Value);

        var jobs = await query
            .OrderByDescending(j => j.StartedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync();

        return Ok(jobs);
    }

    /// <summary>
    /// Get job statistics summary.
    /// </summary>
    /// <returns>Statistics about jobs in the system</returns>
    [HttpGet("stats")]
    [ProducesResponseType(typeof(JobStatistics), StatusCodes.Status200OK)]
    public async Task<ActionResult<JobStatistics>> GetJobStatistics()
    {
        var stats = new JobStatistics
        {
            TotalJobs = await _dbContext.Jobs.CountAsync(),
            PendingJobs = await _dbContext.Jobs.CountAsync(j => j.Status == JobStatus.Pending),
            RunningJobs = await _dbContext.Jobs.CountAsync(j => j.Status == JobStatus.Running),
            CompletedJobs = await _dbContext.Jobs.CountAsync(j => j.Status == JobStatus.Completed),
            FailedJobs = await _dbContext.Jobs.CountAsync(j => j.Status == JobStatus.Failed),
            CancelledJobs = await _dbContext.Jobs.CountAsync(j => j.Status == JobStatus.Cancelled),
            
            AnalysisJobs = await _dbContext.Jobs.CountAsync(j => j.Type == JobType.Analysis),
            GenerationJobs = await _dbContext.Jobs.CountAsync(j => j.Type == JobType.Generation),
            
            AverageCompletionTimeSeconds = await _dbContext.Jobs
                .Where(j => j.Status == JobStatus.Completed && j.CompletedAt != null)
                .Select(j => (j.CompletedAt!.Value - j.StartedAt).TotalSeconds)
                .DefaultIfEmpty(0)
                .AverageAsync()
        };

        return Ok(stats);
    }

    /// <summary>
    /// Cancel a running job.
    /// </summary>
    /// <param name="id">Job ID</param>
    /// <returns>Updated job status</returns>
    [HttpPost("{id}/cancel")]
    [ProducesResponseType(typeof(Job), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<Job>> CancelJob(Guid id)
    {
        var job = await _dbContext.Jobs.FindAsync(id);
        
        if (job == null)
            return NotFound($"Job with ID {id} not found");

        if (job.Status != JobStatus.Pending && job.Status != JobStatus.Running)
            return BadRequest($"Cannot cancel job with status {job.Status}");

        // Update job status
        var updatedJob = job with 
        { 
            Status = JobStatus.Cancelled,
            CompletedAt = DateTime.UtcNow,
            ErrorMessage = "Job cancelled by user"
        };

        _dbContext.Entry(job).CurrentValues.SetValues(updatedJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Job cancelled: {JobId}", id);

        // TODO: Signal orchestration system to cancel the job
        // await CancelOrchestrationAsync(job.OrchestrationInstanceId);

        return Ok(updatedJob);
    }

    /// <summary>
    /// Retry a failed job.
    /// </summary>
    /// <param name="id">Job ID</param>
    /// <returns>New job created for retry</returns>
    [HttpPost("{id}/retry")]
    [ProducesResponseType(typeof(Job), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<Job>> RetryJob(Guid id)
    {
        var originalJob = await _dbContext.Jobs.FindAsync(id);
        
        if (originalJob == null)
            return NotFound($"Job with ID {id} not found");

        if (originalJob.Status != JobStatus.Failed)
            return BadRequest($"Can only retry failed jobs. Current status: {originalJob.Status}");

        // Create new job for retry
        var newJob = new Job
        {
            Id = Guid.NewGuid(),
            Type = originalJob.Type,
            EntityId = originalJob.EntityId,
            OrchestrationInstanceId = string.Empty, // Will be set by orchestration
            Status = JobStatus.Pending,
            StartedAt = DateTime.UtcNow,
            Metadata = new Dictionary<string, object>(originalJob.Metadata)
            {
                ["RetryOf"] = originalJob.Id.ToString(),
                ["RetryAttempt"] = originalJob.Metadata.ContainsKey("RetryAttempt") 
                    ? (int)originalJob.Metadata["RetryAttempt"] + 1 
                    : 1
            }
        };

        _dbContext.Jobs.Add(newJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Job retry created: {NewJobId} (original: {OriginalJobId})", 
            newJob.Id, originalJob.Id);

        // TODO: Trigger orchestration for retry
        // await TriggerOrchestrationAsync(newJob);

        return CreatedAtAction(nameof(GetJob), new { id = newJob.Id }, newJob);
    }

    /// <summary>
    /// Delete a job record.
    /// </summary>
    /// <param name="id">Job ID</param>
    /// <returns>No content on success</returns>
    [HttpDelete("{id}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteJob(Guid id)
    {
        var job = await _dbContext.Jobs.FindAsync(id);
        
        if (job == null)
            return NotFound($"Job with ID {id} not found");

        _dbContext.Jobs.Remove(job);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Job deleted: {JobId}", id);

        return NoContent();
    }
}

/// <summary>
/// Job statistics model for API response.
/// </summary>
public class JobStatistics
{
    public int TotalJobs { get; set; }
    public int PendingJobs { get; set; }
    public int RunningJobs { get; set; }
    public int CompletedJobs { get; set; }
    public int FailedJobs { get; set; }
    public int CancelledJobs { get; set; }
    public int AnalysisJobs { get; set; }
    public int GenerationJobs { get; set; }
    public double AverageCompletionTimeSeconds { get; set; }
}
