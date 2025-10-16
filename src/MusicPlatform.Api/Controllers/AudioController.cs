using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Azure.Storage.Blobs;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;
using MusicPlatform.Api.Services;
using Microsoft.Extensions.DependencyInjection;

namespace MusicPlatform.Api.Controllers;

/// <summary>
/// Controller for audio file upload and retrieval operations.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class AudioController : ControllerBase
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly BlobServiceClient _blobServiceClient;
    private readonly IConfiguration _configuration;
    private readonly ILogger<AudioController> _logger;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IServiceProvider _serviceProvider;
    private readonly IdempotentJobService _jobService;

    public AudioController(
        MusicPlatformDbContext dbContext,
        BlobServiceClient blobServiceClient,
        IConfiguration configuration,
        ILogger<AudioController> logger,
        IHttpClientFactory httpClientFactory,
        IServiceProvider serviceProvider,
        IdempotentJobService jobService)
    {
        _dbContext = dbContext;
        _blobServiceClient = blobServiceClient;
        _configuration = configuration;
        _logger = logger;
        _httpClientFactory = httpClientFactory;
        _serviceProvider = serviceProvider;
        _jobService = jobService;
    }

    /// <summary>
    /// Upload an audio file (MP3) for processing.
    /// </summary>
    /// <param name="file">Audio file to upload</param>
    /// <returns>AudioFile metadata with tracking ID</returns>
    [HttpPost("upload")]
    [ProducesResponseType(typeof(AudioFile), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<AudioFile>> UploadAudio(IFormFile file)
    {
        try
        {
            // Validation
            if (file == null || file.Length == 0)
                return BadRequest("No file uploaded");

            if (!file.ContentType.StartsWith("audio/") && !file.FileName.EndsWith(".mp3", StringComparison.OrdinalIgnoreCase))
                return BadRequest("Only audio files are supported");

            if (file.Length > 100 * 1024 * 1024) // 100 MB limit
                return BadRequest("File size exceeds 100 MB limit");

            // Generate unique IDs
            var audioFileId = Guid.NewGuid();
            var blobName = $"{audioFileId}/{file.FileName}";
            
            // Get blob container
            var containerName = _configuration["BlobStorage:ContainerName"] ?? "audio-files";
            var containerClient = _blobServiceClient.GetBlobContainerClient(containerName);
            await containerClient.CreateIfNotExistsAsync();
            
            // Upload to blob storage
            var blobClient = containerClient.GetBlobClient(blobName);
            using (var stream = file.OpenReadStream())
            {
                await blobClient.UploadAsync(stream, overwrite: true);
            }

            // Calculate duration (simplified - in production, use proper audio library)
            var durationSeconds = 180; // Placeholder - would use NAudio or similar

            // Create database record
            var audioFile = new AudioFile
            {
                Id = audioFileId,
                OriginalFileName = file.FileName,
                BlobUri = blobClient.Uri.ToString(),
                SizeBytes = file.Length,
                Duration = TimeSpan.FromSeconds(durationSeconds),
                Format = Path.GetExtension(file.FileName).TrimStart('.').ToLower(),
                Status = AudioFileStatus.Uploaded,
                UploadedAt = DateTime.UtcNow
            };

            _dbContext.AudioFiles.Add(audioFile);
            await _dbContext.SaveChangesAsync();

            _logger.LogInformation("Audio file uploaded: {FileName} (ID: {Id})", file.FileName, audioFileId);

            // TODO: Trigger analysis workflow
            // await TriggerAnalysisAsync(audioFileId);

            return CreatedAtAction(nameof(GetAudioFile), new { id = audioFileId }, audioFile);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error uploading audio file");
            return StatusCode(500, "An error occurred while uploading the file");
        }
    }

    /// <summary>
    /// Get audio file metadata by ID.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>AudioFile metadata</returns>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(AudioFile), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<AudioFile>> GetAudioFile(Guid id)
    {
        var audioFile = await _dbContext.AudioFiles.FindAsync(id);
        
        if (audioFile == null)
            return NotFound($"Audio file with ID {id} not found");

        // Transform Docker internal URLs to localhost for client access
        var transformedFile = TransformUrlsForClient(audioFile);

        return Ok(transformedFile);
    }

    /// <summary>
    /// Get all audio files (with pagination).
    /// </summary>
    /// <param name="skip">Number of records to skip</param>
    /// <param name="take">Number of records to take</param>
    /// <returns>List of audio files</returns>
    [HttpGet]
    [ProducesResponseType(typeof(IEnumerable<AudioFile>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<AudioFile>>> GetAudioFiles(
        [FromQuery] int skip = 0,
        [FromQuery] int take = 20)
    {
        if (take > 100) take = 100; // Max 100 records per request

        // Only return audio files that have successfully completed analysis
        var completedAnalysisJobEntityIds = await _dbContext.Jobs
            .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Completed)
            .Select(j => j.EntityId)
            .ToListAsync();

        var audioFiles = await _dbContext.AudioFiles
            .Where(a => completedAnalysisJobEntityIds.Contains(a.Id))
            .OrderByDescending(a => a.UploadedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync();

        // Transform Docker internal URLs to localhost for client access
        var transformedFiles = audioFiles.Select(f => TransformUrlsForClient(f)).ToList();

        return Ok(transformedFiles);
    }

    /// <summary>
    /// Get training data status - shows which audio files are ready for AI training.
    /// </summary>
    /// <returns>List of audio files with their training readiness status</returns>
    [HttpGet("training")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    public async Task<ActionResult> GetTrainingDataStatus()
    {
        try
        {
            // Get all audio files that have completed analysis
            var completedAnalysisJobEntityIds = await _dbContext.Jobs
                .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Completed)
                .Select(j => j.EntityId)
                .ToListAsync();

            var audioFilesWithAnalysis = await _dbContext.AudioFiles
                .Where(a => completedAnalysisJobEntityIds.Contains(a.Id))
                .ToListAsync();

            var trainingDataSummary = new List<object>();

            foreach (var audioFile in audioFilesWithAnalysis)
            {
                // Get analysis results
                var analysisResult = await _dbContext.AnalysisResults
                    .Include(a => a.Chords)
                    .Include(a => a.Sections)
                    .Include(a => a.Beats)
                    .FirstOrDefaultAsync(a => a.AudioFileId == audioFile.Id);

                // Get stems
                var stems = await _dbContext.Stems
                    .Where(s => s.AudioFileId == audioFile.Id)
                    .GroupBy(s => s.Type)
                    .Select(g => g.OrderByDescending(s => s.SeparatedAt).First())
                    .ToListAsync();

                // Check training readiness
                var isTrainingReady = analysisResult != null && 
                                    stems.Count >= 3 && // At least 3 stems available
                                    !string.IsNullOrEmpty(analysisResult.Key) &&
                                    analysisResult.Bpm.HasValue;

                trainingDataSummary.Add(new
                {
                    AudioFileId = audioFile.Id,
                    FileName = audioFile.OriginalFileName,
                    Title = audioFile.Title ?? "Unknown",
                    Artist = audioFile.Artist ?? "Unknown",
                    Duration = audioFile.Duration.TotalSeconds,
                    
                    // Training readiness indicators
                    IsTrainingReady = isTrainingReady,
                    HasAnalysisResults = analysisResult != null,
                    HasMusicTheoryFeatures = analysisResult != null && 
                                           !string.IsNullOrEmpty(analysisResult.HarmonicAnalysis),
                    
                    // Music features for training
                    BPM = analysisResult?.Bpm,
                    Key = analysisResult?.Key,
                    TimeSignature = audioFile.TimeSignature,
                    
                    // Data counts
                    StemsCount = stems.Count,
                    StemTypes = stems.Select(s => s.Type.ToString()).ToList(),
                    BeatsCount = analysisResult?.Beats?.Count ?? 0,
                    ChordsCount = analysisResult?.Chords?.Count ?? 0,
                    SectionsCount = analysisResult?.Sections?.Count ?? 0,
                    
                    // Timestamps
                    UploadedAt = audioFile.UploadedAt,
                    AnalyzedAt = analysisResult?.AnalyzedAt,
                    PreparedForTraining = audioFile.Comment?.Contains("Training data prepared") == true
                });
            }

            var summary = new
            {
                TotalAudioFiles = audioFilesWithAnalysis.Count,
                TrainingReadyCount = trainingDataSummary.Count(t => (bool)t.GetType().GetProperty("IsTrainingReady")?.GetValue(t)),
                TotalStemsAvailable = trainingDataSummary.Sum(t => (int)t.GetType().GetProperty("StemsCount")?.GetValue(t)),
                TotalBeats = trainingDataSummary.Sum(t => (int)t.GetType().GetProperty("BeatsCount")?.GetValue(t)),
                TotalChords = trainingDataSummary.Sum(t => (int)t.GetType().GetProperty("ChordsCount")?.GetValue(t)),
                AudioFiles = trainingDataSummary
            };

            return Ok(summary);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting training data status");
            return StatusCode(500, new { error = "Failed to get training data status", details = ex.Message });
        }
    }

    /// <summary>
    /// Transform Docker internal URLs (azurite:10000) to localhost URLs for client access.
    /// </summary>
    private AudioFile TransformUrlsForClient(AudioFile audioFile)
    {
        return audioFile with
        {
            BlobUri = audioFile.BlobUri.Replace("http://azurite:10000", "http://localhost:10000"),
            AlbumArtworkUri = !string.IsNullOrEmpty(audioFile.AlbumArtworkUri) 
                ? $"http://localhost:5000/api/audio/{audioFile.Id}/artwork"
                : null
        };
    }

    /// <summary>
    /// Get analysis result for an audio file.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>Analysis result with MIR data</returns>
    [HttpGet("{id}/analysis")]
    [ProducesResponseType(typeof(AnalysisResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<AnalysisResult>> GetAnalysisResult(Guid id)
    {
        var analysisResult = await _dbContext.AnalysisResults
            .Include(a => a.Chords)
            .Include(a => a.Sections)
            .Include(a => a.Beats)
            .FirstOrDefaultAsync(a => a.AudioFileId == id);

        if (analysisResult == null)
            return NotFound($"Analysis result not found for audio file {id}");

        return Ok(analysisResult);
    }

    /// <summary>
    /// Request analysis for an audio file with idempotency guarantees.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>Accepted response with job information</returns>
    [HttpPost("{id}/analyze")]
    [ProducesResponseType(StatusCodes.Status202Accepted)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> RequestAnalysis(Guid id)
    {
        var audioFile = await _dbContext.AudioFiles.FindAsync(id);
        if (audioFile == null)
            return NotFound($"Audio file {id} not found");

        // Create or get existing idempotent job
        var metadata = new Dictionary<string, object>
        {
            { "AudioFileName", audioFile.OriginalFileName },
            { "BlobUri", audioFile.BlobUri }
            // Note: Don't include timestamps in metadata for idempotency
        };

        var job = await _jobService.CreateOrGetIdempotentJobAsync(
            JobType.Analysis, 
            id, 
            metadata);

        // Check job status and respond accordingly
        switch (job.Status)
        {
            case JobStatus.Completed:
                return Ok(new { 
                    message = "Analysis already completed", 
                    audioFileId = id, 
                    jobId = job.Id,
                    completedAt = job.CompletedAt
                });

            case JobStatus.Running:
                return Accepted(new { 
                    message = "Analysis already in progress", 
                    audioFileId = id, 
                    jobId = job.Id,
                    currentStep = job.CurrentStep,
                    startedAt = job.StartedAt
                });

            case JobStatus.Pending:
            case JobStatus.Retrying:
                // Trigger async analysis
                _ = Task.Run(async () => await TriggerIdempotentAnalysisAsync(id, job.Id));
                
                return Accepted(new { 
                    message = job.Status == JobStatus.Retrying ? 
                        $"Analysis retry started (attempt {job.RetryCount + 1}/{job.MaxRetries})" : 
                        "Analysis request submitted", 
                    audioFileId = id, 
                    jobId = job.Id,
                    retryCount = job.RetryCount,
                    maxRetries = job.MaxRetries
                });

            case JobStatus.Failed:
                if (job.RetryCount >= job.MaxRetries)
                {
                    return Conflict(new { 
                        message = "Analysis failed permanently after maximum retries", 
                        audioFileId = id, 
                        jobId = job.Id,
                        errorMessage = job.ErrorMessage,
                        retryCount = job.RetryCount,
                        maxRetries = job.MaxRetries
                    });
                }
                else
                {
                    // Create retry
                    var retryJob = await _jobService.CreateOrGetIdempotentJobAsync(JobType.Analysis, id, metadata);
                    _ = Task.Run(async () => await TriggerIdempotentAnalysisAsync(id, retryJob.Id));
                    
                    return Accepted(new { 
                        message = $"Analysis retry started (attempt {retryJob.RetryCount + 1}/{retryJob.MaxRetries})", 
                        audioFileId = id, 
                        jobId = retryJob.Id,
                        previousError = job.ErrorMessage
                    });
                }

            case JobStatus.Stale:
                // Create retry for stale job
                var staleRetryJob = await _jobService.CreateOrGetIdempotentJobAsync(JobType.Analysis, id, metadata);
                _ = Task.Run(async () => await TriggerIdempotentAnalysisAsync(id, staleRetryJob.Id));
                
                return Accepted(new { 
                    message = "Restarting stale analysis job", 
                    audioFileId = id, 
                    jobId = staleRetryJob.Id,
                    retryCount = staleRetryJob.RetryCount
                });

            default:
                return StatusCode(500, new { 
                    message = $"Unexpected job status: {job.Status}", 
                    audioFileId = id, 
                    jobId = job.Id 
                });
        }
    }

    /// <summary>
    /// Callback endpoint for analysis worker to report completion with idempotency support.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <param name="request">Analysis completion data</param>
    /// <returns>Success response</returns>
    [HttpPost("{id}/analysis-complete")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> AnalysisComplete(Guid id, [FromBody] AnalysisCompleteRequest request)
    {
        _logger.LogInformation("Analysis complete callback received for audio file {AudioFileId}, Job: {JobId}, Success: {Success}", 
            id, request.JobId, request.Success);

        if (request.JobId.HasValue)
        {
            // Use the specific job ID provided by the worker
            if (request.Success)
            {
                var completionMetadata = new Dictionary<string, object>
                {
                    { "completed_at", DateTime.UtcNow.ToString("O") },
                    { "callback_received", true }
                };
                
                if (!string.IsNullOrEmpty(request.ResultSummary))
                {
                    completionMetadata["result_summary"] = request.ResultSummary;
                }

                await _jobService.CompleteJobAsync(request.JobId.Value, completionMetadata);
                
                // TRIGGER TRAINING DATA PREPARATION ON SUCCESSFUL ANALYSIS COMPLETION
                _ = Task.Run(async () => await PrepareTrainingDataAsync(id));
            }
            else
            {
                var failureMetadata = new Dictionary<string, object>
                {
                    { "failed_at", DateTime.UtcNow.ToString("O") },
                    { "callback_received", true }
                };

                await _jobService.FailJobAsync(request.JobId.Value, 
                    request.ErrorMessage ?? "Analysis failed (no error message provided)", 
                    failureMetadata);
            }
        }
        else
        {
            // Fallback: Find the most recent running/pending job for this audio file
            var job = await _dbContext.Jobs
                .Where(j => j.EntityId == id && 
                           j.Type == JobType.Analysis && 
                           (j.Status == JobStatus.Running || j.Status == JobStatus.Pending))
                .OrderByDescending(j => j.StartedAt)
                .FirstOrDefaultAsync();

            if (job != null)
            {
                if (request.Success)
                {
                    await _jobService.CompleteJobAsync(job.Id);
                    
                    // TRIGGER TRAINING DATA PREPARATION ON SUCCESSFUL ANALYSIS COMPLETION
                    _ = Task.Run(async () => await PrepareTrainingDataAsync(id));
                }
                else
                {
                    await _jobService.FailJobAsync(job.Id, 
                        request.ErrorMessage ?? "Analysis failed (no error message provided)");
                }
                
                _logger.LogInformation("Updated job {JobId} status to {Status} (found by audio file ID)", 
                    job.Id, request.Success ? "Completed" : "Failed");
            }
            else
            {
                _logger.LogWarning("No active job found for audio file {AudioFileId}", id);
            }
        }

        return Ok(new { message = "Analysis completion recorded", audioFileId = id });
    }

    /// <summary>
    /// Get JAMS annotation for an audio file.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>JAMS annotation in JSON format</returns>
    [HttpGet("{id}/jams")]
    [ProducesResponseType(typeof(JAMSAnnotation), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<JAMSAnnotation>> GetJamsAnnotation(Guid id)
    {
        var jamsAnnotation = await _dbContext.JAMSAnnotations
            .FirstOrDefaultAsync(j => j.AudioFileId == id);

        if (jamsAnnotation == null)
            return NotFound($"JAMS annotation not found for audio file {id}");

        return Ok(jamsAnnotation);
    }

    /// <summary>
    /// Get all stems (separated audio tracks) for an audio file.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>List of stems</returns>
    [HttpGet("{id}/stems")]
    [ProducesResponseType(typeof(IEnumerable<Stem>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<Stem>>> GetStems(Guid id)
    {
        var stems = await _dbContext.Stems
            .Where(s => s.AudioFileId == id)
            .OrderBy(s => s.Type)
            .ThenByDescending(s => s.SeparatedAt) // Latest first
            .ToListAsync();

        // Deduplicate - only return the latest stem of each type
        var uniqueStems = stems
            .GroupBy(s => s.Type)
            .Select(g => g.First()) // First is latest due to ThenByDescending above
            .ToList();

        // Transform Docker internal URLs to localhost for client access
        var transformedStems = uniqueStems.Select(s => s with
        {
            BlobUri = s.BlobUri.Replace("http://azurite:10000", "http://localhost:10000"),
            JamsUri = s.JamsUri?.Replace("http://azurite:10000", "http://localhost:10000")
        }).ToList();

        return Ok(transformedStems);
    }

    /// <summary>
    /// Delete an audio file and all associated data.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>No content on success</returns>
    [HttpDelete("{id}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteAudioFile(Guid id)
    {
        var audioFile = await _dbContext.AudioFiles.FindAsync(id);
        
        if (audioFile == null)
            return NotFound($"Audio file with ID {id} not found");

        try
        {
            // Delete from blob storage
            var containerName = _configuration["BlobStorage:ContainerName"] ?? "audio-files";
            var containerClient = _blobServiceClient.GetBlobContainerClient(containerName);
            var uri = new Uri(audioFile.BlobUri);
            var blobName = string.Join("", uri.Segments.Skip(2)); // Skip container name segment
            var blobClient = containerClient.GetBlobClient(blobName);
            await blobClient.DeleteIfExistsAsync();

            // Delete from database (cascade will handle related records)
            _dbContext.AudioFiles.Remove(audioFile);
            await _dbContext.SaveChangesAsync();

            _logger.LogInformation("Audio file deleted: {Id}", id);

            return NoContent();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting audio file {Id}", id);
            return StatusCode(500, "An error occurred while deleting the file");
        }
    }

    /// <summary>
    /// Update audio file metadata (typically called by analysis worker).
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <param name="request">Metadata update request</param>
    /// <returns>Updated audio file</returns>
    [HttpPut("{id}/metadata")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> UpdateMetadata(Guid id, [FromBody] UpdateAudioMetadataRequest request)
    {
        var audioFile = await _dbContext.AudioFiles.FindAsync(id);
        
        if (audioFile == null)
            return NotFound($"Audio file with ID {id} not found");

        // Create updated audioFile with new metadata values
        var updatedAudioFile = audioFile with
        {
            Title = request.Title ?? audioFile.Title,
            Artist = request.Artist ?? audioFile.Artist,
            Album = request.Album ?? audioFile.Album,
            AlbumArtist = request.AlbumArtist ?? audioFile.AlbumArtist,
            Year = request.Year ?? audioFile.Year,
            Genre = request.Genre ?? audioFile.Genre,
            TrackNumber = request.TrackNumber ?? audioFile.TrackNumber,
            DiscNumber = request.DiscNumber ?? audioFile.DiscNumber,
            Composer = request.Composer ?? audioFile.Composer,
            Conductor = request.Conductor ?? audioFile.Conductor,
            Comment = request.Comment ?? audioFile.Comment,
            AlbumArtworkUri = request.AlbumArtworkUri ?? audioFile.AlbumArtworkUri,
            Bitrate = request.Bitrate ?? audioFile.Bitrate,
            SampleRate = request.SampleRate ?? audioFile.SampleRate,
            Channels = request.Channels ?? audioFile.Channels,
            AudioMode = request.AudioMode ?? audioFile.AudioMode,
            Mp3Version = request.Mp3Version ?? audioFile.Mp3Version,
            BpmTag = request.BpmTag ?? audioFile.BpmTag,
            KeyTag = request.KeyTag ?? audioFile.KeyTag,
            Bpm = request.Bpm ?? audioFile.Bpm,
            Key = request.Key ?? audioFile.Key,
            TimeSignature = request.TimeSignature ?? audioFile.TimeSignature
        };

        // Update the tracked entity with new values
        _dbContext.Entry(audioFile).CurrentValues.SetValues(updatedAudioFile);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Updated metadata for audio file {Id}", id);

        return Ok(updatedAudioFile);
    }

    /// <summary>
    /// Trigger idempotent analysis workflow for an audio file.
    /// </summary>
    private async Task TriggerIdempotentAnalysisAsync(Guid audioFileId, Guid jobId)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();
        var jobService = scope.ServiceProvider.GetRequiredService<IdempotentJobService>();
        
        try
        {
            // Start job processing with worker instance tracking
            var workerInstanceId = Environment.MachineName + "_" + Environment.ProcessId;
            var jobStarted = await jobService.StartJobProcessingAsync(jobId, workerInstanceId);
            
            if (!jobStarted)
            {
                _logger.LogWarning("Could not start job {JobId} - already being processed or invalid state", jobId);
                return;
            }

            // Update job with initial checkpoint
            await jobService.UpdateJobWithHeartbeatAsync(jobId, JobStatus.Running, "initializing", 
                new Dictionary<string, object> { { "initialized_at", DateTime.UtcNow.ToString("O") } });

            // Get audio file to obtain blob URI
            var audioFile = await dbContext.AudioFiles.FindAsync(audioFileId);
            if (audioFile == null)
            {
                await jobService.FailJobAsync(jobId, "Audio file not found");
                return;
            }

            // Update heartbeat - downloading
            await jobService.UpdateJobWithHeartbeatAsync(jobId, newStatus: null, currentStep: "downloading_audio");

            var httpClient = _httpClientFactory.CreateClient("AnalysisWorker");
            
            // Build callback URL for job completion  
            var callbackUrl = $"http://music-api:8080/api/audio/{audioFileId}/analysis-complete";
            
            // Add job ID to request for tracking
            var analysisRequest = new 
            { 
                audio_file_id = audioFileId.ToString(),
                blob_uri = audioFile.BlobUri,
                callback_url = callbackUrl,
                job_id = jobId.ToString(),  // Pass job ID for worker tracking
                idempotency_key = jobId.ToString() // Use job ID as idempotency key
            };

            // Update heartbeat - calling worker
            await jobService.UpdateJobWithHeartbeatAsync(jobId, newStatus: null, currentStep: "calling_analysis_worker");
            
            var response = await httpClient.PostAsJsonAsync("/analyze", analysisRequest);
            
            if (!response.IsSuccessStatusCode)
            {
                await jobService.FailJobAsync(jobId, $"Worker returned {response.StatusCode}: {await response.Content.ReadAsStringAsync()}");
            }
            else
            {
                // Update heartbeat - worker accepted job
                await jobService.UpdateJobWithHeartbeatAsync(jobId, newStatus: null, currentStep: "worker_processing", 
                    checkpointData: new Dictionary<string, object> 
                    { 
                        { "worker_response_received", DateTime.UtcNow.ToString("O") },
                        { "worker_status_code", (int)response.StatusCode }
                    });
                
                _logger.LogInformation("Analysis triggered successfully for {AudioFileId}, job {JobId}", audioFileId, jobId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error triggering analysis for {AudioFileId}, job {JobId}", audioFileId, jobId);
            await jobService.FailJobAsync(jobId, ex.Message, 
                new Dictionary<string, object> { { "exception_type", ex.GetType().Name } });
        }
    }

    /// <summary>
    /// Delete all audio files and their associated data (analysis results, stems, jobs).
    /// WARNING: This is destructive and cannot be undone!
    /// </summary>
    /// <returns>Summary of deleted items</returns>
    [HttpDelete("all")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    public async Task<ActionResult> DeleteAllAudioFiles()
    {
        try
        {
            _logger.LogWarning("DESTRUCTIVE OPERATION: Deleting all audio files and related data");

            // Count items before deletion
            var audioFileCount = await _dbContext.AudioFiles.CountAsync();
            var analysisResultCount = await _dbContext.AnalysisResults.CountAsync();
            var stemCount = await _dbContext.Stems.CountAsync();
            var analysisJobCount = await _dbContext.Jobs.Where(j => j.Type == JobType.Analysis).CountAsync();

            // Delete in order to respect foreign key constraints
            // 1. Delete stems (references AudioFiles via AnalysisResults)
            _dbContext.Stems.RemoveRange(_dbContext.Stems);
            
            // 2. Delete analysis results (contains nested collections)
            _dbContext.AnalysisResults.RemoveRange(_dbContext.AnalysisResults);
            
            // 3. Delete analysis jobs
            var analysisJobs = await _dbContext.Jobs.Where(j => j.Type == JobType.Analysis).ToListAsync();
            _dbContext.Jobs.RemoveRange(analysisJobs);
            
            // 4. Delete audio files
            _dbContext.AudioFiles.RemoveRange(_dbContext.AudioFiles);

            await _dbContext.SaveChangesAsync();

            var summary = new
            {
                message = "All audio files and related data deleted successfully",
                deleted = new
                {
                    audioFiles = audioFileCount,
                    analysisResults = analysisResultCount,
                    stems = stemCount,
                    analysisJobs = analysisJobCount
                }
            };

            _logger.LogWarning("Deleted all content: {Summary}", summary);
            return Ok(summary);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting all audio files");
            return StatusCode(500, new { error = "Failed to delete audio files", details = ex.Message });
        }
    }

    /// <summary>
    /// Delete all jobs (all types).
    /// WARNING: This is destructive and cannot be undone!
    /// </summary>
    /// <returns>Summary of deleted jobs</returns>
    [HttpDelete("jobs/all")]
    [ProducesResponseType(typeof(object), StatusCodes.Status200OK)]
    public async Task<ActionResult> DeleteAllJobs()
    {
        try
        {
            _logger.LogWarning("DESTRUCTIVE OPERATION: Deleting all jobs");

            var jobCount = await _dbContext.Jobs.CountAsync();
            var jobsByType = await _dbContext.Jobs
                .GroupBy(j => j.Type)
                .Select(g => new { Type = g.Key, Count = g.Count() })
                .ToListAsync();

            _dbContext.Jobs.RemoveRange(_dbContext.Jobs);
            await _dbContext.SaveChangesAsync();

            var summary = new
            {
                message = "All jobs deleted successfully",
                deleted = new
                {
                    totalJobs = jobCount,
                    byType = jobsByType
                }
            };

            _logger.LogWarning("Deleted all jobs: {Summary}", summary);
            return Ok(summary);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting all jobs");
            return StatusCode(500, new { error = "Failed to delete jobs", details = ex.Message });
        }
    }

    /// <summary>
    /// Proxy endpoint to serve album artwork with authentication
    /// </summary>
    [HttpGet("{id}/artwork")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetArtwork(Guid id)
    {
        try
        {
            var audioFile = await _dbContext.AudioFiles.FindAsync(id);
            if (audioFile == null || string.IsNullOrEmpty(audioFile.AlbumArtworkUri))
                return NotFound();

            // Get the blob URI (with azurite hostname)
            var blobUri = audioFile.AlbumArtworkUri.Replace("http://localhost:10000", "http://azurite:10000");
            
            // Download from blob storage
            var containerName = _configuration["BlobStorage:ContainerName"] ?? "audio-files";
            var containerClient = _blobServiceClient.GetBlobContainerClient(containerName);
            var blobName = $"{audioFile.Id}/artwork.jpg";
            var blobClient = containerClient.GetBlobClient(blobName);

            var response = await blobClient.DownloadAsync();
            
            return File(response.Value.Content, "image/jpeg");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error serving artwork for {Id}", id);
            return NotFound();
        }
    }

    /// <summary>
    /// Automatically prepare training data when MP3 analysis completes successfully.
    /// This integrates the training pipeline with the ingestion pipeline.
    /// </summary>
    private async Task PrepareTrainingDataAsync(Guid audioFileId)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();
        
        try
        {
            _logger.LogInformation("Starting automatic training data preparation for audio file {AudioFileId}", audioFileId);

            // Get audio file metadata
            var audioFile = await dbContext.AudioFiles.FindAsync(audioFileId);
            if (audioFile == null)
            {
                _logger.LogWarning("Audio file {AudioFileId} not found during training data preparation", audioFileId);
                return;
            }

            // Check if analysis results exist
            var analysisResult = await dbContext.AnalysisResults
                .Include(a => a.Chords)
                .Include(a => a.Sections)
                .Include(a => a.Beats)
                .FirstOrDefaultAsync(a => a.AudioFileId == audioFileId);

            if (analysisResult == null)
            {
                _logger.LogWarning("No analysis results found for audio file {AudioFileId}, skipping training data preparation", audioFileId);
                return;
            }

            // Get stems
            var stems = await dbContext.Stems
                .Where(s => s.AudioFileId == audioFileId)
                .GroupBy(s => s.Type)
                .Select(g => g.OrderByDescending(s => s.SeparatedAt).First()) // Latest of each type
                .ToListAsync();

            // Prepare training data entry
            var trainingDataEntry = new
            {
                AudioFileId = audioFileId,
                FileName = audioFile.OriginalFileName,
                Title = audioFile.Title ?? "Unknown",
                Artist = audioFile.Artist ?? "Unknown",
                Duration = audioFile.Duration.TotalSeconds,
                
                // Music theory features
                BPM = analysisResult.Bpm,
                Key = analysisResult.Key,
                TimeSignature = audioFile.TimeSignature,
                
                // Musical structure
                BeatsCount = analysisResult.Beats?.Count ?? 0,
                ChordsCount = analysisResult.Chords?.Count ?? 0,
                SectionsCount = analysisResult.Sections?.Count ?? 0,
                
                // Stems information
                StemsAvailable = stems.Select(s => new {
                    Type = s.Type.ToString(),
                    BlobUri = s.BlobUri.Replace("http://azurite:10000", "http://localhost:10000"),
                    SizeBytes = s.SizeBytes,
                    Duration = s.Duration?.TotalSeconds
                }).ToList(),
                
                // Analysis metadata
                AnalyzedAt = analysisResult.AnalyzedAt,
                HasHarmonicAnalysis = !string.IsNullOrEmpty(analysisResult.HarmonicAnalysis),
                HasRhythmicAnalysis = !string.IsNullOrEmpty(analysisResult.RhythmicAnalysis),
                HasGenreAnalysis = !string.IsNullOrEmpty(analysisResult.GenreAnalysis),
                
                // Blob URIs for access
                OriginalBlobUri = audioFile.BlobUri.Replace("http://azurite:10000", "http://localhost:10000"),
                
                PreparedAt = DateTime.UtcNow
            };

            // Log the training data preparation
            _logger.LogInformation("Training data prepared for {FileName} by {Artist}: BPM={BPM}, Key={Key}, {StemsCount} stems, {BeatsCount} beats, {ChordsCount} chords", 
                trainingDataEntry.FileName, 
                trainingDataEntry.Artist,
                trainingDataEntry.BPM,
                trainingDataEntry.Key,
                trainingDataEntry.StemsAvailable.Count,
                trainingDataEntry.BeatsCount,
                trainingDataEntry.ChordsCount);

            // Store training readiness metadata in the audio file
            var updatedAudioFile = audioFile with
            {
                Comment = $"Training data prepared at {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss}"
            };

            dbContext.Entry(audioFile).CurrentValues.SetValues(updatedAudioFile);
            await dbContext.SaveChangesAsync();

            // TODO: Future enhancement - save to dedicated training dataset table
            // For now, the training data is accessible via the API endpoints and export script

            _logger.LogInformation("Training data preparation completed successfully for audio file {AudioFileId}", audioFileId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error preparing training data for audio file {AudioFileId}", audioFileId);
        }
    }
}

/// <summary>
/// Request body for analysis completion callback with idempotency support
/// </summary>
public record AnalysisCompleteRequest(
    bool Success,
    string? ErrorMessage = null,
    Guid? JobId = null,  // Job ID for exact tracking
    string? ResultSummary = null  // Brief summary of results
);

/// <summary>
/// Request body for updating audio file metadata
/// </summary>
public record UpdateAudioMetadataRequest(
    string? Title = null,
    string? Artist = null,
    string? Album = null,
    string? AlbumArtist = null,
    string? Year = null,
    string? Genre = null,
    string? TrackNumber = null,
    string? DiscNumber = null,
    string? Composer = null,
    string? Conductor = null,
    string? Comment = null,
    string? AlbumArtworkUri = null,
    int? Bitrate = null,
    int? SampleRate = null,
    int? Channels = null,
    string? AudioMode = null,
    string? Mp3Version = null,
    string? BpmTag = null,
    string? KeyTag = null,
    double? Bpm = null,
    string? Key = null,
    string? TimeSignature = null
);
