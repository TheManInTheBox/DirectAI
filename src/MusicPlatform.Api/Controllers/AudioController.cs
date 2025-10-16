using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Azure.Storage.Blobs;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;

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

    public AudioController(
        MusicPlatformDbContext dbContext,
        BlobServiceClient blobServiceClient,
        IConfiguration configuration,
        ILogger<AudioController> logger,
        IHttpClientFactory httpClientFactory)
    {
        _dbContext = dbContext;
        _blobServiceClient = blobServiceClient;
        _configuration = configuration;
        _logger = logger;
        _httpClientFactory = httpClientFactory;
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

        return Ok(audioFile);
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

        var audioFiles = await _dbContext.AudioFiles
            .OrderByDescending(a => a.UploadedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync();

        return Ok(audioFiles);
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
            .FirstOrDefaultAsync(a => a.AudioFileId == id);

        if (analysisResult == null)
            return NotFound($"Analysis result not found for audio file {id}");

        return Ok(analysisResult);
    }

    /// <summary>
    /// Request analysis for an audio file.
    /// </summary>
    /// <param name="id">Audio file ID</param>
    /// <returns>Accepted response</returns>
    [HttpPost("{id}/analyze")]
    [ProducesResponseType(StatusCodes.Status202Accepted)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> RequestAnalysis(Guid id)
    {
        var audioFile = await _dbContext.AudioFiles.FindAsync(id);
        if (audioFile == null)
            return NotFound($"Audio file {id} not found");

        // Trigger async analysis
        await TriggerAnalysisAsync(id);

        return Accepted(new { message = "Analysis request submitted", audioFileId = id });
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
            .ToListAsync();

        return Ok(stems);
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
    /// Trigger analysis workflow for an audio file (internal use).
    /// </summary>
    private async Task TriggerAnalysisAsync(Guid audioFileId)
    {
        try
        {
            // Get audio file to obtain blob URI
            var audioFile = await _dbContext.AudioFiles.FindAsync(audioFileId);
            if (audioFile == null)
            {
                _logger.LogWarning("Audio file {AudioFileId} not found when triggering analysis", audioFileId);
                return;
            }

            var httpClient = _httpClientFactory.CreateClient("AnalysisWorker");
            var response = await httpClient.PostAsJsonAsync("/analyze", new 
            { 
                audio_file_id = audioFileId.ToString(),
                blob_uri = audioFile.BlobUri
            });
            
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("Failed to trigger analysis for {AudioFileId}: {StatusCode}", 
                    audioFileId, response.StatusCode);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error triggering analysis for {AudioFileId}", audioFileId);
        }
    }
}
