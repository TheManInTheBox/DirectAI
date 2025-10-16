using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;
using System.Security.Cryptography;
using System.Text;

namespace MusicPlatform.Api.Services;

/// <summary>
/// Service for managing idempotent job processing.
/// Ensures jobs can be safely retried, resumed, and don't create duplicates.
/// </summary>
public class IdempotentJobService
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly ILogger<IdempotentJobService> _logger;
    private readonly IConfiguration _configuration;

    public IdempotentJobService(
        MusicPlatformDbContext dbContext,
        ILogger<IdempotentJobService> logger,
        IConfiguration configuration)
    {
        _dbContext = dbContext;
        _logger = logger;
        _configuration = configuration;
    }

    /// <summary>
    /// Creates or returns existing job with idempotency guarantees.
    /// </summary>
    /// <param name="jobType">Type of job to create</param>
    /// <param name="entityId">Entity ID (e.g., AudioFile ID)</param>
    /// <param name="metadata">Job metadata</param>
    /// <returns>New or existing job</returns>
    public async Task<Job> CreateOrGetIdempotentJobAsync(
        JobType jobType,
        Guid entityId,
        Dictionary<string, object>? metadata = null)
    {
        var idempotencyKey = GenerateIdempotencyKey(jobType, entityId, metadata);
        
        // Check for existing job with same idempotency key
        var existingJob = await _dbContext.Jobs
            .Where(j => j.IdempotencyKey == idempotencyKey)
            .OrderByDescending(j => j.StartedAt)
            .FirstOrDefaultAsync();

        if (existingJob != null)
        {
            _logger.LogInformation("Found existing job {JobId} with idempotency key {Key}", 
                existingJob.Id, idempotencyKey);

            // If job is completed or failed with max retries, return it
            if (existingJob.Status == JobStatus.Completed || 
                (existingJob.Status == JobStatus.Failed && existingJob.RetryCount >= existingJob.MaxRetries))
            {
                return existingJob;
            }

            // If job is running but stale, mark it for retry
            if (existingJob.Status == JobStatus.Running && IsJobStale(existingJob))
            {
                _logger.LogWarning("Job {JobId} appears stale, marking for retry", existingJob.Id);
                var staleJob = existingJob with
                {
                    Status = JobStatus.Stale,
                    ErrorMessage = "Job marked as stale due to missing heartbeat"
                };
                _dbContext.Entry(existingJob).CurrentValues.SetValues(staleJob);
                await _dbContext.SaveChangesAsync();
                
                // Create retry job
                return await CreateRetryJobAsync(staleJob);
            }

            // If job is pending, running, or retrying (and not stale), return existing
            if (existingJob.Status == JobStatus.Pending || 
                existingJob.Status == JobStatus.Running || 
                existingJob.Status == JobStatus.Retrying)
            {
                return existingJob;
            }

            // If job was cancelled or failed but can be retried, create retry
            if (existingJob.Status == JobStatus.Cancelled || 
                (existingJob.Status == JobStatus.Failed && existingJob.RetryCount < existingJob.MaxRetries))
            {
                _logger.LogInformation("Retrying {Status} job {JobId}", existingJob.Status, existingJob.Id);
                return await CreateRetryJobAsync(existingJob);
            }
        }

        // Create new job
        var maxRetries = GetMaxRetriesForJobType(jobType);
        var newJob = new Job
        {
            Id = Guid.NewGuid(),
            Type = jobType,
            EntityId = entityId,
            Status = JobStatus.Pending,
            StartedAt = DateTime.UtcNow,
            Metadata = metadata ?? new Dictionary<string, object>(),
            IdempotencyKey = idempotencyKey,
            RetryCount = 0,
            MaxRetries = maxRetries,
            Checkpoints = new Dictionary<string, object>()
        };

        _dbContext.Jobs.Add(newJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Created new idempotent job {JobId} for {JobType} on entity {EntityId}", 
            newJob.Id, jobType, entityId);

        return newJob;
    }

    /// <summary>
    /// Updates job status with heartbeat for liveness tracking.
    /// </summary>
    public async Task UpdateJobWithHeartbeatAsync(Guid jobId, JobStatus? newStatus = null, 
        string? currentStep = null, Dictionary<string, object>? checkpointData = null)
    {
        var job = await _dbContext.Jobs.FindAsync(jobId);
        if (job == null)
        {
            _logger.LogWarning("Attempted to update non-existent job {JobId}", jobId);
            return;
        }

        var updatedCheckpoints = new Dictionary<string, object>(job.Checkpoints);
        if (checkpointData != null)
        {
            foreach (var kvp in checkpointData)
            {
                updatedCheckpoints[kvp.Key] = kvp.Value;
            }
        }

        var updatedJob = job with
        {
            Status = newStatus ?? job.Status,
            LastHeartbeat = DateTime.UtcNow,
            CurrentStep = currentStep ?? job.CurrentStep,
            Checkpoints = updatedCheckpoints
        };

        _dbContext.Entry(job).CurrentValues.SetValues(updatedJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogDebug("Updated job {JobId} heartbeat, status: {Status}, step: {Step}", 
            jobId, updatedJob.Status, currentStep);
    }

    /// <summary>
    /// Completes a job successfully and schedules it for deletion.
    /// </summary>
    public async Task CompleteJobAsync(Guid jobId, Dictionary<string, object>? finalMetadata = null, bool autoDelete = true)
    {
        var job = await _dbContext.Jobs.FindAsync(jobId);
        if (job == null)
        {
            _logger.LogWarning("Attempted to complete non-existent job {JobId}", jobId);
            return;
        }

        var updatedMetadata = new Dictionary<string, object>(job.Metadata);
        if (finalMetadata != null)
        {
            foreach (var kvp in finalMetadata)
            {
                updatedMetadata[kvp.Key] = kvp.Value;
            }
        }

        var completedJob = job with
        {
            Status = JobStatus.Completed,
            CompletedAt = DateTime.UtcNow,
            LastHeartbeat = DateTime.UtcNow,
            Metadata = updatedMetadata
        };

        _dbContext.Entry(job).CurrentValues.SetValues(completedJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Completed job {JobId} successfully", jobId);

        // Schedule job for automatic deletion after 30 seconds
        if (autoDelete)
        {
            _ = Task.Run(async () =>
            {
                await Task.Delay(TimeSpan.FromSeconds(30));
                await DeleteCompletedJobAsync(jobId);
            });
        }
    }

    /// <summary>
    /// Deletes a completed job from the database.
    /// </summary>
    public async Task DeleteCompletedJobAsync(Guid jobId)
    {
        try
        {
            var job = await _dbContext.Jobs.FindAsync(jobId);
            if (job != null && job.Status == JobStatus.Completed)
            {
                _dbContext.Jobs.Remove(job);
                await _dbContext.SaveChangesAsync();
                _logger.LogInformation("Deleted completed job {JobId}", jobId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting completed job {JobId}", jobId);
        }
    }

    /// <summary>
    /// Fails a job with error message.
    /// </summary>
    public async Task FailJobAsync(Guid jobId, string errorMessage, 
        Dictionary<string, object>? failureMetadata = null)
    {
        var job = await _dbContext.Jobs.FindAsync(jobId);
        if (job == null)
        {
            _logger.LogWarning("Attempted to fail non-existent job {JobId}", jobId);
            return;
        }

        var updatedMetadata = new Dictionary<string, object>(job.Metadata);
        if (failureMetadata != null)
        {
            foreach (var kvp in failureMetadata)
            {
                updatedMetadata[kvp.Key] = kvp.Value;
            }
        }

        var failedJob = job with
        {
            Status = JobStatus.Failed,
            CompletedAt = DateTime.UtcNow,
            LastHeartbeat = DateTime.UtcNow,
            ErrorMessage = errorMessage,
            Metadata = updatedMetadata
        };

        _dbContext.Entry(job).CurrentValues.SetValues(failedJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogWarning("Failed job {JobId}: {ErrorMessage}", jobId, errorMessage);
    }

    /// <summary>
    /// Gets resumable checkpoint data for a job.
    /// </summary>
    public async Task<Dictionary<string, object>?> GetJobCheckpointsAsync(Guid jobId)
    {
        var job = await _dbContext.Jobs.FindAsync(jobId);
        return job?.Checkpoints;
    }

    /// <summary>
    /// Cleans up stale jobs that have been running too long without heartbeat.
    /// </summary>
    public async Task CleanupStaleJobsAsync()
    {
        var staleThreshold = DateTime.UtcNow.AddMinutes(-30); // 30 minutes without heartbeat

        var staleJobs = await _dbContext.Jobs
            .Where(j => j.Status == JobStatus.Running && 
                       (j.LastHeartbeat == null || j.LastHeartbeat < staleThreshold))
            .ToListAsync();

        foreach (var staleJob in staleJobs)
        {
            var updatedJob = staleJob with
            {
                Status = JobStatus.Stale,
                ErrorMessage = "Job marked as stale due to missing heartbeat for 30+ minutes"
            };

            _dbContext.Entry(staleJob).CurrentValues.SetValues(updatedJob);
            _logger.LogWarning("Marked job {JobId} as stale", staleJob.Id);
        }

        if (staleJobs.Any())
        {
            await _dbContext.SaveChangesAsync();
            _logger.LogInformation("Cleaned up {Count} stale jobs", staleJobs.Count);
        }
    }

    /// <summary>
    /// Cleans up old failed and cancelled jobs.
    /// </summary>
    public async Task CleanupOldJobsAsync(int daysOld = 7)
    {
        var cleanupThreshold = DateTime.UtcNow.AddDays(-daysOld);

        var oldJobs = await _dbContext.Jobs
            .Where(j => (j.Status == JobStatus.Failed || j.Status == JobStatus.Cancelled) && 
                       j.CompletedAt != null && 
                       j.CompletedAt < cleanupThreshold)
            .ToListAsync();

        if (oldJobs.Any())
        {
            _dbContext.Jobs.RemoveRange(oldJobs);
            await _dbContext.SaveChangesAsync();
            _logger.LogInformation("Cleaned up {Count} old failed/cancelled jobs older than {Days} days", 
                oldJobs.Count, daysOld);
        }
    }

    /// <summary>
    /// Starts processing a job (marks as running with worker instance).
    /// </summary>
    public async Task<bool> StartJobProcessingAsync(Guid jobId, string workerInstanceId)
    {
        var job = await _dbContext.Jobs.FindAsync(jobId);
        if (job == null || (job.Status != JobStatus.Pending && job.Status != JobStatus.Retrying))
        {
            return false;
        }

        var runningJob = job with
        {
            Status = JobStatus.Running,
            LastHeartbeat = DateTime.UtcNow,
            WorkerInstanceId = workerInstanceId
        };

        _dbContext.Entry(job).CurrentValues.SetValues(runningJob);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Started processing job {JobId} on worker {WorkerId}", 
            jobId, workerInstanceId);
        return true;
    }

    #region Private Methods

    private string GenerateIdempotencyKey(JobType jobType, Guid entityId, 
        Dictionary<string, object>? metadata)
    {
        // Create a deterministic key based on job type, entity, and critical metadata
        var keyData = $"{jobType}:{entityId}";
        
        // Add relevant metadata to key (only non-temporal data)
        if (metadata != null)
        {
            var relevantKeys = metadata.Keys
                .Where(k => !k.Contains("timestamp", StringComparison.OrdinalIgnoreCase) &&
                           !k.Contains("time", StringComparison.OrdinalIgnoreCase))
                .OrderBy(k => k);
            
            foreach (var key in relevantKeys)
            {
                keyData += $":{key}={metadata[key]}";
            }
        }

        // Generate SHA256 hash for consistent key length
        using var sha256 = SHA256.Create();
        var hashBytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(keyData));
        return Convert.ToHexString(hashBytes).ToLower();
    }

    private bool IsJobStale(Job job)
    {
        var staleThreshold = DateTime.UtcNow.AddMinutes(-15); // 15 minutes without heartbeat
        return job.LastHeartbeat == null || job.LastHeartbeat < staleThreshold;
    }

    private async Task<Job> CreateRetryJobAsync(Job failedJob)
    {
        using var transaction = await _dbContext.Database.BeginTransactionAsync();
        
        try
        {
            // If the failed job is in a terminal state (Cancelled, Failed, Stale),
            // we need to remove it from the database first to avoid idempotency key conflicts
            if (failedJob.Status == JobStatus.Cancelled || 
                failedJob.Status == JobStatus.Failed ||
                failedJob.Status == JobStatus.Stale)
            {
                _logger.LogInformation("Removing terminal job {JobId} (status: {Status}) before creating retry", 
                    failedJob.Id, failedJob.Status);
                
                // Detach the entity if it's being tracked
                var entry = _dbContext.Entry(failedJob);
                if (entry.State != EntityState.Detached)
                {
                    entry.State = EntityState.Detached;
                }
                
                // Now find and remove the job from the database
                var jobToRemove = await _dbContext.Jobs.FindAsync(failedJob.Id);
                if (jobToRemove != null)
                {
                    _dbContext.Jobs.Remove(jobToRemove);
                    await _dbContext.SaveChangesAsync();
                }
            }

            var retryJob = failedJob with
            {
                Id = Guid.NewGuid(),
                Status = JobStatus.Retrying,
                StartedAt = DateTime.UtcNow,
                CompletedAt = null,
                LastHeartbeat = null,
                RetryCount = failedJob.RetryCount + 1,
                ErrorMessage = null,
                WorkerInstanceId = null
            };

            _dbContext.Jobs.Add(retryJob);
            await _dbContext.SaveChangesAsync();

            await transaction.CommitAsync();

            _logger.LogInformation("Created retry job {JobId} (attempt {RetryCount}/{MaxRetries}) for failed job {OriginalJobId}", 
                retryJob.Id, retryJob.RetryCount, retryJob.MaxRetries, failedJob.Id);

            return retryJob;
        }
        catch
        {
            await transaction.RollbackAsync();
            throw;
        }
    }

    private int GetMaxRetriesForJobType(JobType jobType)
    {
        return jobType switch
        {
            JobType.Analysis => _configuration.GetValue("Jobs:MaxRetries:Analysis", 3),
            JobType.Generation => _configuration.GetValue("Jobs:MaxRetries:Generation", 2),
            JobType.SourceSeparation => _configuration.GetValue("Jobs:MaxRetries:SourceSeparation", 2),
            _ => _configuration.GetValue("Jobs:MaxRetries:Default", 2)
        };
    }

    #endregion
}
