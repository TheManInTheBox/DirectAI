using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;
using MusicPlatform.Api.Services;

namespace MusicPlatform.Api.Controllers;

/// <summary>
/// Controller for audio stem generation requests and management.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class GenerationController : ControllerBase
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly ILogger<GenerationController> _logger;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IdempotentJobService _jobService;
    private readonly IServiceProvider _serviceProvider;

    public GenerationController(
        MusicPlatformDbContext dbContext,
        ILogger<GenerationController> logger,
        IHttpClientFactory httpClientFactory,
        IdempotentJobService jobService,
        IServiceProvider serviceProvider)
    {
        _dbContext = dbContext;
        _logger = logger;
        _httpClientFactory = httpClientFactory;
        _jobService = jobService;
        _serviceProvider = serviceProvider;
    }

    /// <summary>
    /// Create a new generation request for AI-generated stems.
    /// </summary>
    /// <param name="request">Generation request parameters</param>
    /// <returns>Created generation request with tracking ID</returns>
    [HttpPost]
    [ProducesResponseType(typeof(GenerationRequest), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<GenerationRequest>> CreateGenerationRequest(
        [FromBody] CreateGenerationRequestDto request)
    {
        // Validate audio file exists
        var audioFile = await _dbContext.AudioFiles.FindAsync(request.AudioFileId);
        if (audioFile == null)
            return NotFound($"Audio file with ID {request.AudioFileId} not found");

        // Validate analysis is complete (optional, but recommended)
        var hasAnalysis = await _dbContext.AnalysisResults
            .AnyAsync(a => a.AudioFileId == request.AudioFileId);
        
        if (!hasAnalysis)
        {
            _logger.LogWarning("Generation requested for audio file {AudioFileId} without analysis", 
                request.AudioFileId);
        }

        // Create generation request
        var generationRequest = new GenerationRequest
        {
            Id = Guid.NewGuid(),
            AudioFileId = request.AudioFileId,
            TargetStems = request.TargetStems,
            Parameters = new GenerationParameters
            {
                TargetBpm = request.Parameters?.TargetBpm,
                DurationSeconds = request.Parameters?.DurationSeconds ?? 10.0f,
                Style = request.Parameters?.Style,
                ChordProgression = request.Parameters?.ChordProgression,
                Prompt = request.Parameters?.Prompt,
                Temperature = request.Parameters?.Temperature ?? 1.0f,
                RandomSeed = request.Parameters?.RandomSeed
            },
            RequestedAt = DateTime.UtcNow,
            Status = GenerationStatus.Pending
        };

        _dbContext.GenerationRequests.Add(generationRequest);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Generation request created: {RequestId} for audio file {AudioFileId}", 
            generationRequest.Id, request.AudioFileId);

        // Create job for generation workflow
        var metadata = new Dictionary<string, object>
        {
            { "AudioFileName", audioFile.OriginalFileName },
            { "TargetStems", string.Join(",", request.TargetStems.Select(s => s.ToString())) },
            { "GenerationRequestId", generationRequest.Id.ToString() }
        };

        var job = await _jobService.CreateOrGetIdempotentJobAsync(
            JobType.Generation,
            generationRequest.Id,
            metadata);

        // Trigger generation workflow asynchronously
        if (job.Status == JobStatus.Pending || job.Status == JobStatus.Retrying)
        {
            _ = Task.Run(async () => await TriggerGenerationAsync(generationRequest.Id, job.Id));
            _logger.LogInformation("Generation job {JobId} triggered for request {RequestId}", 
                job.Id, generationRequest.Id);
        }

        return CreatedAtAction(nameof(GetGenerationRequest), 
            new { id = generationRequest.Id }, generationRequest);
    }

    /// <summary>
    /// Get generation request by ID.
    /// </summary>
    /// <param name="id">Generation request ID</param>
    /// <returns>Generation request details</returns>
    [HttpGet("{id}")]
    [ProducesResponseType(typeof(GenerationRequest), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<GenerationRequest>> GetGenerationRequest(Guid id)
    {
        var generationRequest = await _dbContext.GenerationRequests.FindAsync(id);
        
        if (generationRequest == null)
            return NotFound($"Generation request with ID {id} not found");

        return Ok(generationRequest);
    }

    /// <summary>
    /// Get all generation requests for an audio file.
    /// </summary>
    /// <param name="audioFileId">Audio file ID</param>
    /// <returns>List of generation requests</returns>
    [HttpGet("audio/{audioFileId}")]
    [ProducesResponseType(typeof(IEnumerable<GenerationRequest>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<GenerationRequest>>> GetGenerationRequestsByAudioFile(
        Guid audioFileId)
    {
        var requests = await _dbContext.GenerationRequests
            .Where(g => g.AudioFileId == audioFileId)
            .OrderByDescending(g => g.RequestedAt)
            .ToListAsync();

        return Ok(requests);
    }

    /// <summary>
    /// Get all generation requests (with filtering and pagination).
    /// </summary>
    /// <param name="status">Optional status filter</param>
    /// <param name="skip">Number of records to skip</param>
    /// <param name="take">Number of records to take</param>
    /// <returns>List of generation requests</returns>
    [HttpGet]
    [ProducesResponseType(typeof(IEnumerable<GenerationRequest>), StatusCodes.Status200OK)]
    public async Task<ActionResult<IEnumerable<GenerationRequest>>> GetGenerationRequests(
        [FromQuery] GenerationStatus? status = null,
        [FromQuery] int skip = 0,
        [FromQuery] int take = 20)
    {
        if (take > 100) take = 100; // Max 100 records per request

        var query = _dbContext.GenerationRequests.AsQueryable();

        if (status.HasValue)
            query = query.Where(g => g.Status == status.Value);

        var requests = await query
            .OrderByDescending(g => g.RequestedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync();

        return Ok(requests);
    }

    /// <summary>
    /// Get generated stems for a generation request.
    /// </summary>
    /// <param name="id">Generation request ID</param>
    /// <returns>List of generated stems</returns>
    [HttpGet("{id}/stems")]
    [ProducesResponseType(typeof(IEnumerable<GeneratedStem>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<IEnumerable<GeneratedStem>>> GetGeneratedStems(Guid id)
    {
        // Verify request exists
        var requestExists = await _dbContext.GenerationRequests
            .AnyAsync(g => g.Id == id);

        if (!requestExists)
            return NotFound($"Generation request with ID {id} not found");

        var stems = await _dbContext.GeneratedStems
            .Where(s => s.GenerationRequestId == id)
            .OrderBy(s => s.GeneratedAt)
            .ToListAsync();

        return Ok(stems);
    }

    /// <summary>
    /// Download a generated stem file.
    /// </summary>
    /// <param name="stemId">Generated stem ID</param>
    /// <returns>Audio file stream</returns>
    /// <summary>
    /// Download a generated stem file from blob storage.
    /// </summary>
    [HttpGet("download-stem/{stemId}")]
    [ProducesResponseType(typeof(FileStreamResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DownloadGeneratedStem(Guid stemId)
    {
        var stem = await _dbContext.GeneratedStems.FindAsync(stemId);
        if (stem == null)
        {
            return NotFound($"Generated stem with ID {stemId} not found");
        }

        try
        {
            // Get the blob service client from DI
            using var scope = _serviceProvider.CreateScope();
            var blobServiceClient = scope.ServiceProvider.GetRequiredService<Azure.Storage.Blobs.BlobServiceClient>();

            // Parse the blob URI to extract container and blob name
            var blobUri = new Uri(stem.BlobUri);
            var pathParts = blobUri.AbsolutePath.TrimStart('/').Split('/', 2);
            
            if (pathParts.Length < 2)
            {
                return BadRequest("Invalid blob URI format");
            }

            var containerName = pathParts[0];  // "audio-files"
            var blobName = pathParts[1];        // "generated/guid/track.wav"

            _logger.LogInformation("Downloading generated stem {StemId}: container={Container}, blob={BlobName}", 
                stemId, containerName, blobName);

            // Get blob client
            var containerClient = blobServiceClient.GetBlobContainerClient(containerName);
            var blobClient = containerClient.GetBlobClient(blobName);

            // Check if blob exists
            var exists = await blobClient.ExistsAsync();
            _logger.LogInformation("Blob exists check for {BlobName}: {Exists}", blobName, exists.Value);
            
            if (!exists.Value)
            {
                return NotFound("Generated stem file not found in storage");
            }

            // Download blob and stream to client
            var download = await blobClient.DownloadStreamingAsync();
            
            // Set appropriate headers
            var fileName = $"{stem.Type}_{stem.Id}.{stem.Format}";
            Response.Headers.Append("Content-Disposition", $"attachment; filename=\"{fileName}\"");
            
            return File(download.Value.Content, $"audio/{stem.Format}");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error downloading generated stem {StemId}", stemId);
            return StatusCode(500, $"Error downloading generated stem: {ex.Message}");
        }
    }

    /// <summary>
    /// Cancel a pending or running generation request.
    /// </summary>
    /// <param name="id">Generation request ID</param>
    /// <returns>Updated generation request</returns>
    [HttpPost("{id}/cancel")]
    [ProducesResponseType(typeof(GenerationRequest), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<GenerationRequest>> CancelGenerationRequest(Guid id)
    {
        var request = await _dbContext.GenerationRequests.FindAsync(id);
        
        if (request == null)
            return NotFound($"Generation request with ID {id} not found");

        if (request.Status == GenerationStatus.Completed || request.Status == GenerationStatus.Failed)
            return BadRequest($"Cannot cancel request with status {request.Status}");

        // Update request status
        var updatedRequest = request with 
        { 
            Status = GenerationStatus.Failed,
            CompletedAt = DateTime.UtcNow,
            ErrorMessage = "Cancelled by user"
        };

        _dbContext.Entry(request).CurrentValues.SetValues(updatedRequest);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Generation request cancelled: {RequestId}", id);

        // TODO: Signal generation worker to cancel
        // await CancelGenerationWorkAsync(id);

        return Ok(updatedRequest);
    }

    /// <summary>
    /// Delete a generation request and all generated stems.
    /// </summary>
    /// <param name="id">Generation request ID</param>
    /// <returns>No content on success</returns>
    [HttpDelete("{id}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteGenerationRequest(Guid id)
    {
        var request = await _dbContext.GenerationRequests.FindAsync(id);
        
        if (request == null)
            return NotFound($"Generation request with ID {id} not found");

        // Delete from database (cascade will handle generated stems)
        _dbContext.GenerationRequests.Remove(request);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Generation request deleted: {RequestId}", id);

        // TODO: Delete generated stem blobs from storage

        return NoContent();
    }

    /// <summary>
    /// Callback endpoint for generation worker to report completion.
    /// </summary>
    /// <param name="id">Generation request ID</param>
    /// <param name="result">Generation result payload from worker</param>
    /// <returns>Accepted response</returns>
    [HttpPost("{id}/complete")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GenerationComplete(Guid id, [FromBody] GenerationResultDto result)
    {
        _logger.LogInformation("Received generation completion callback for request {RequestId}, status: {Status}", 
            id, result.Status);

        // Find the generation request
        var request = await _dbContext.GenerationRequests.FindAsync(id);
        if (request == null)
        {
            _logger.LogWarning("Generation request {RequestId} not found for completion callback", id);
            return NotFound($"Generation request with ID {id} not found");
        }

        // Find the associated job
        var job = await _dbContext.Jobs
            .FirstOrDefaultAsync(j => j.Type == JobType.Generation && j.EntityId == id);

        if (result.Status == "completed")
        {
            // Update generation request
            var completedRequest = request with
            {
                Status = GenerationStatus.Completed,
                CompletedAt = DateTime.UtcNow
            };
            _dbContext.Entry(request).CurrentValues.SetValues(completedRequest);

            // Save generated track info
            if (result.Track != null)
            {
                // Calculate duration from sample rate and file size
                // WAV file: file_size_bytes / (sample_rate * channels * bytes_per_sample)
                // Assuming 16-bit (2 bytes per sample)
                float durationSeconds = 0;
                if (result.Track.SampleRate > 0 && result.Track.Channels > 0 && result.Track.FileSizeBytes > 0)
                {
                    int bytesPerSample = 2; // 16-bit audio
                    long dataBytes = result.Track.FileSizeBytes - 44; // WAV header is typically 44 bytes
                    if (dataBytes > 0)
                    {
                        durationSeconds = (float)dataBytes / (result.Track.SampleRate * result.Track.Channels * bytesPerSample);
                    }
                }
                
                var generatedStem = new GeneratedStem
                {
                    Id = Guid.NewGuid(),
                    GenerationRequestId = id,
                    Type = StemType.Other, // Use "Other" for full track
                    BlobUri = result.Track.BlobUrl,
                    DurationSeconds = durationSeconds,
                    Format = result.Track.Format,
                    SampleRate = result.Track.SampleRate,
                    Channels = result.Track.Channels,
                    GeneratedAt = DateTime.UtcNow,
                    Metadata = new GenerationMetadata()
                };
                _dbContext.GeneratedStems.Add(generatedStem);
                _logger.LogInformation("Saved generated track for request {RequestId}: {BlobUrl}, Duration: {Duration}s, Size: {Size} bytes", 
                    id, result.Track.BlobUrl, durationSeconds, result.Track.FileSizeBytes);
            }

            // Update job
            if (job != null)
            {
                var completedJob = job with
                {
                    Status = JobStatus.Completed,
                    CurrentStep = "generation_complete",
                    CompletedAt = DateTime.UtcNow,
                    LastHeartbeat = DateTime.UtcNow
                };
                _dbContext.Entry(job).CurrentValues.SetValues(completedJob);
            }

            _logger.LogInformation("Generation request {RequestId} completed successfully in {ProcessingTime}s", 
                id, result.ProcessingTimeSeconds);
        }
        else if (result.Status == "failed")
        {
            // Update generation request
            var failedRequest = request with
            {
                Status = GenerationStatus.Failed,
                CompletedAt = DateTime.UtcNow,
                ErrorMessage = result.Error
            };
            _dbContext.Entry(request).CurrentValues.SetValues(failedRequest);

            // Update job
            if (job != null)
            {
                var failedJob = job with
                {
                    Status = JobStatus.Failed,
                    ErrorMessage = result.Error,
                    CompletedAt = DateTime.UtcNow,
                    LastHeartbeat = DateTime.UtcNow
                };
                _dbContext.Entry(job).CurrentValues.SetValues(failedJob);
            }

            _logger.LogWarning("Generation request {RequestId} failed: {Error}", id, result.Error);
        }

        await _dbContext.SaveChangesAsync();

        return Ok(new { message = "Generation completion processed successfully" });
    }

    /// <summary>
    /// Trigger generation workflow (internal use).
    /// </summary>
    private async Task TriggerGenerationAsync(Guid generationRequestId, Guid jobId)
    {
        // Create a new scope to avoid DbContext disposal issues
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<MusicPlatformDbContext>();
        
        try
        {
            _logger.LogInformation("Triggering generation worker for request {RequestId}, job {JobId}", 
                generationRequestId, jobId);

            // Get the generation request
            var request = await dbContext.GenerationRequests
                .FirstOrDefaultAsync(r => r.Id == generationRequestId);

            if (request == null)
            {
                _logger.LogError("Generation request {RequestId} not found", generationRequestId);
                return;
            }

            // Update job status to Running
            var job = await dbContext.Jobs.FindAsync(jobId);
            if (job != null)
            {
                var runningJob = job with
                {
                    Status = JobStatus.Running,
                    CurrentStep = "triggering_worker",
                    LastHeartbeat = DateTime.UtcNow
                };
                dbContext.Entry(job).CurrentValues.SetValues(runningJob);
                await dbContext.SaveChangesAsync();
            }

            // Call generation worker API
            var httpClient = _httpClientFactory.CreateClient("GenerationWorker");
            
            var payload = new
            {
                generation_request_id = generationRequestId.ToString(),
                audio_file_id = request.AudioFileId.ToString(),
                parameters = new
                {
                    target_bpm = request.Parameters?.TargetBpm,
                    duration_seconds = request.Parameters?.DurationSeconds ?? 10.0,
                    style = request.Parameters?.Style,
                    chord_progression = request.Parameters?.ChordProgression,
                    prompt = request.Parameters?.Prompt,
                    temperature = request.Parameters?.Temperature ?? 1.0,
                    random_seed = request.Parameters?.RandomSeed
                },
                callback_url = $"{Request.Scheme}://{Request.Host}/api/generation/callback"
            };

            var response = await httpClient.PostAsJsonAsync("/generate", payload);
            
            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync();
                _logger.LogWarning("Failed to trigger generation for {RequestId}: {StatusCode} - {Error}", 
                    generationRequestId, response.StatusCode, errorContent);
                
                // Mark job as failed
                if (job != null)
                {
                    var failedJob = job with
                    {
                        Status = JobStatus.Failed,
                        ErrorMessage = $"Worker returned {response.StatusCode}: {errorContent}",
                        CompletedAt = DateTime.UtcNow
                    };
                    dbContext.Entry(job).CurrentValues.SetValues(failedJob);
                    await dbContext.SaveChangesAsync();
                }
                
                // Update generation request status
                var failedRequest = request with
                {
                    Status = GenerationStatus.Failed,
                    CompletedAt = DateTime.UtcNow,
                    ErrorMessage = $"Worker trigger failed: {response.StatusCode}"
                };
                dbContext.Entry(request).CurrentValues.SetValues(failedRequest);
                await dbContext.SaveChangesAsync();
            }
            else
            {
                _logger.LogInformation("Successfully triggered generation worker for request {RequestId}", 
                    generationRequestId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error triggering generation for {RequestId}", 
                generationRequestId);
            
            // Update job status to failed
            var job = await dbContext.Jobs.FindAsync(jobId);
            if (job != null)
            {
                var failedJob = job with
                {
                    Status = JobStatus.Failed,
                    ErrorMessage = $"Exception during trigger: {ex.Message}",
                    CompletedAt = DateTime.UtcNow
                };
                dbContext.Entry(job).CurrentValues.SetValues(failedJob);
                await dbContext.SaveChangesAsync();
            }
        }
    }
}

/// <summary>
/// DTO for creating a generation request.
/// </summary>
public class CreateGenerationRequestDto
{
    public Guid AudioFileId { get; set; }
    public List<StemType> TargetStems { get; set; } = new();
    public GenerationParametersDto? Parameters { get; set; }
}

/// <summary>
/// DTO for generation parameters.
/// </summary>
public class GenerationParametersDto
{
    public float? TargetBpm { get; set; }
    public float? DurationSeconds { get; set; }
    public string? Style { get; set; }
    public List<string>? ChordProgression { get; set; }
    public string? Prompt { get; set; }
    public float? Temperature { get; set; }
    public int? RandomSeed { get; set; }
    
    // Musical parameters for trained model generation
    public string? Key { get; set; }  // e.g., "C", "D#", "Bb"
    public string? Scale { get; set; }  // e.g., "major", "minor", "dorian", "mixolydian"
    public string? TimeSignature { get; set; }  // e.g., "4/4", "3/4", "6/8", "7/8"
    public int? Bars { get; set; }  // Number of bars to generate
    
    // For trained model generation
    public Guid? TrainedModelId { get; set; }  // Use custom trained model instead of base MusicGen
}

/// <summary>
/// DTO for generation completion callback from worker.
/// </summary>
public class GenerationResultDto
{
    [System.Text.Json.Serialization.JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;  // "completed" or "failed"
    
    [System.Text.Json.Serialization.JsonPropertyName("processing_time_seconds")]
    public float? ProcessingTimeSeconds { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("track")]
    public GeneratedTrackDto? Track { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("error")]
    public string? Error { get; set; }
}

/// <summary>
/// DTO for generated track info.
/// </summary>
public class GeneratedTrackDto
{
    [System.Text.Json.Serialization.JsonPropertyName("blob_url")]
    public string BlobUrl { get; set; } = string.Empty;
    
    [System.Text.Json.Serialization.JsonPropertyName("file_size_bytes")]
    public long FileSizeBytes { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("format")]
    public string Format { get; set; } = "wav";
    
    [System.Text.Json.Serialization.JsonPropertyName("sample_rate")]
    public int SampleRate { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("channels")]
    public int Channels { get; set; }
}
