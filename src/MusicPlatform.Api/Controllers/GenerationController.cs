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
                job_id = jobId.ToString(),
                audio_file_id = request.AudioFileId.ToString(),
                target_stems = request.TargetStems.Select(s => s.ToString().ToLower()).ToList(),
                parameters = new
                {
                    target_bpm = request.Parameters?.TargetBpm,
                    duration_seconds = request.Parameters?.DurationSeconds,
                    style = request.Parameters?.Style,
                    chord_progression = request.Parameters?.ChordProgression,
                    prompt = request.Parameters?.Prompt,
                    temperature = request.Parameters?.Temperature,
                    random_seed = request.Parameters?.RandomSeed
                }
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
