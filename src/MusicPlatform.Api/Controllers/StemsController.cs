using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;
using MusicPlatform.Infrastructure.Data;

namespace MusicPlatform.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class StemsController : ControllerBase
{
    private readonly MusicPlatformDbContext _dbContext;
    private readonly ILogger<StemsController> _logger;
    private readonly Azure.Storage.Blobs.BlobServiceClient _blobServiceClient;
    private readonly IConfiguration _configuration;

    public StemsController(
        MusicPlatformDbContext dbContext, 
        ILogger<StemsController> logger,
        Azure.Storage.Blobs.BlobServiceClient blobServiceClient,
        IConfiguration configuration)
    {
        _dbContext = dbContext;
        _logger = logger;
        _blobServiceClient = blobServiceClient;
        _configuration = configuration;
    }

    /// <summary>
    /// Get all stems for a specific audio file
    /// </summary>
    [HttpGet("audio/{audioFileId}")]
    public async Task<ActionResult<List<StemDto>>> GetStemsByAudioFile(Guid audioFileId)
    {
        var stems = await _dbContext.Stems
            .Include(s => s.AudioFile)
            .Where(s => s.AudioFileId == audioFileId)
            .OrderBy(s => s.Type)
            .ToListAsync();

        var stemDtos = stems.Select(StemDto.FromStem).ToList();
        return Ok(stemDtos);
    }

    /// <summary>
    /// Get a specific stem by ID
    /// </summary>
    [HttpGet("{id}")]
    public async Task<ActionResult<StemDto>> GetStem(Guid id)
    {
        var stem = await _dbContext.Stems
            .Include(s => s.AudioFile)
            .FirstOrDefaultAsync(s => s.Id == id);
            
        if (stem == null)
        {
            return NotFound($"Stem with ID {id} not found");
        }

        return Ok(StemDto.FromStem(stem));
    }

    /// <summary>
    /// Get stems filtered by type
    /// </summary>
    [HttpGet("type/{type}")]
    public async Task<ActionResult<List<StemDto>>> GetStemsByType(StemType type)
    {
        var stems = await _dbContext.Stems
            .Where(s => s.Type == type)
            .OrderByDescending(s => s.SeparatedAt)
            .ToListAsync();

        var stemDtos = stems.Select(StemDto.FromStem).ToList();
        return Ok(stemDtos);
    }

    /// <summary>
    /// Get stems filtered by musical key
    /// </summary>
    [HttpGet("key/{key}")]
    public async Task<ActionResult<List<StemDto>>> GetStemsByKey(string key)
    {
        var stems = await _dbContext.Stems
            .Where(s => s.Key == key && s.AnalysisStatus == StemAnalysisStatus.Completed)
            .OrderBy(s => s.Type)
            .ToListAsync();

        var stemDtos = stems.Select(StemDto.FromStem).ToList();
        return Ok(stemDtos);
    }

    /// <summary>
    /// Get stems within a BPM range
    /// </summary>
    [HttpGet("bpm")]
    public async Task<ActionResult<List<StemDto>>> GetStemsByBpmRange(
        [FromQuery] double? minBpm = null,
        [FromQuery] double? maxBpm = null)
    {
        var query = _dbContext.Stems
            .Where(s => s.Bpm != null && s.AnalysisStatus == StemAnalysisStatus.Completed);

        if (minBpm.HasValue)
            query = query.Where(s => s.Bpm >= minBpm.Value);

        if (maxBpm.HasValue)
            query = query.Where(s => s.Bpm <= maxBpm.Value);

        var stems = await query
            .OrderBy(s => s.Bpm)
            .ToListAsync();

        var stemDtos = stems.Select(StemDto.FromStem).ToList();
        return Ok(stemDtos);
    }

    /// <summary>
    /// Create a new stem record (typically called by analysis worker)
    /// </summary>
    [HttpPost]
    public async Task<ActionResult<StemDto>> CreateStem([FromBody] CreateStemRequest request)
    {
        var stem = new Stem
        {
            Id = Guid.NewGuid(),
            AudioFileId = request.AudioFileId,
            Type = request.Type,
            BlobUri = request.BlobUri,
            DurationSeconds = request.DurationSeconds,
            FileSizeBytes = request.FileSizeBytes,
            SeparatedAt = DateTime.UtcNow,
            SourceSeparationModel = request.SourceSeparationModel,
            
            // Musical metadata (can be null initially and populated later)
            Bpm = request.Bpm,
            Key = request.Key,
            TimeSignature = request.TimeSignature,
            TuningFrequency = request.TuningFrequency,
            
            // Audio quality metrics
            RmsLevel = request.RmsLevel,
            PeakLevel = request.PeakLevel,
            SpectralCentroid = request.SpectralCentroid,
            ZeroCrossingRate = request.ZeroCrossingRate,
            
            // Musical structure (JSON strings)
            ChordProgression = request.ChordProgression,
            Beats = request.Beats,
            Sections = request.Sections,
            NotationData = request.NotationData,
            FlamingoInsightsJson = request.FlamingoInsightsJson,
            
            // JAMS annotation URI
            JamsUri = request.JamsUri,
            
            // Analysis tracking
            AnalysisStatus = request.AnalysisStatus ?? StemAnalysisStatus.Pending,
            AnalysisErrorMessage = request.AnalysisErrorMessage,
            AnalyzedAt = request.AnalyzedAt
        };

        _dbContext.Stems.Add(stem);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Created stem {StemId} of type {StemType} for audio file {AudioFileId}", 
            stem.Id, stem.Type, stem.AudioFileId);

        return CreatedAtAction(nameof(GetStem), new { id = stem.Id }, StemDto.FromStem(stem));
    }

    /// <summary>
    /// Update stem analysis metadata (typically called by analysis worker)
    /// </summary>
    [HttpPut("{id}/analysis")]
    public async Task<ActionResult<StemDto>> UpdateStemAnalysis(Guid id, [FromBody] UpdateStemAnalysisRequest request)
    {
        var stem = await _dbContext.Stems.FindAsync(id);
        if (stem == null)
        {
            return NotFound($"Stem with ID {id} not found");
        }

        // Update analysis fields
        stem = stem with
        {
            Bpm = request.Bpm ?? stem.Bpm,
            Key = request.Key ?? stem.Key,
            TimeSignature = request.TimeSignature ?? stem.TimeSignature,
            TuningFrequency = request.TuningFrequency ?? stem.TuningFrequency,
            RmsLevel = request.RmsLevel ?? stem.RmsLevel,
            PeakLevel = request.PeakLevel ?? stem.PeakLevel,
            SpectralCentroid = request.SpectralCentroid ?? stem.SpectralCentroid,
            ZeroCrossingRate = request.ZeroCrossingRate ?? stem.ZeroCrossingRate,
            ChordProgression = request.ChordProgression ?? stem.ChordProgression,
            Beats = request.Beats ?? stem.Beats,
            Sections = request.Sections ?? stem.Sections,
            NotationData = request.NotationData ?? stem.NotationData,
            FlamingoInsightsJson = request.FlamingoInsightsJson ?? stem.FlamingoInsightsJson,
            JamsUri = request.JamsUri ?? stem.JamsUri,
            AnalysisStatus = request.AnalysisStatus,
            AnalysisErrorMessage = request.AnalysisErrorMessage,
            AnalyzedAt = request.AnalysisStatus == StemAnalysisStatus.Completed ? DateTime.UtcNow : stem.AnalyzedAt
        };

        _dbContext.Stems.Update(stem);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Updated analysis for stem {StemId} with status {AnalysisStatus}", 
            stem.Id, stem.AnalysisStatus);

        return Ok(StemDto.FromStem(stem));
    }

    /// <summary>
    /// Delete a stem
    /// </summary>
    [HttpDelete("{id}")]
    public async Task<IActionResult> DeleteStem(Guid id)
    {
        var stem = await _dbContext.Stems.FindAsync(id);
        if (stem == null)
        {
            return NotFound($"Stem with ID {id} not found");
        }

        _dbContext.Stems.Remove(stem);
        await _dbContext.SaveChangesAsync();

        _logger.LogInformation("Deleted stem {StemId}", id);
        return NoContent();
    }

    /// <summary>
    /// Download stem file
    /// </summary>
    [HttpGet("{id}/download")]
    public async Task<IActionResult> DownloadStem(Guid id)
    {
        var stem = await _dbContext.Stems.FindAsync(id);
        if (stem == null)
        {
            return NotFound($"Stem with ID {id} not found");
        }

        try
        {
            // Parse Azure blob URI to extract container and blob name
            // Azure format: https://accountname.blob.core.windows.net/container-name/blob-path
            var blobUri = new Uri(stem.BlobUri);
            var pathParts = blobUri.AbsolutePath.TrimStart('/').Split('/', 2);
            
            if (pathParts.Length != 2)
            {
                return BadRequest("Invalid Azure blob URI format");
            }

            var containerName = pathParts[0];  // "audio-files"
            var blobName = pathParts[1];       // "guid/stems/type.wav"

            _logger.LogInformation("Downloading stem {StemId}: container={Container}, blob={BlobName}", 
                id, containerName, blobName);

            // Get blob client
            var containerClient = _blobServiceClient.GetBlobContainerClient(containerName);
            var blobClient = containerClient.GetBlobClient(blobName);

            // Check if blob exists
            var exists = await blobClient.ExistsAsync();
            _logger.LogInformation("Blob exists check for {BlobName}: {Exists}", blobName, exists.Value);
            
            if (!exists.Value)
            {
                return NotFound("Stem file not found in storage");
            }

            // Download blob and stream to client
            var download = await blobClient.DownloadStreamingAsync();
            
            // Set appropriate headers
            Response.Headers.Append("Content-Disposition", $"attachment; filename=\"{stem.Type}_{stem.Id}.wav\"");
            
            return File(download.Value.Content, "audio/wav");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error downloading stem {StemId}", id);
            return StatusCode(500, $"Error downloading stem: {ex.Message}");
        }
    }

    /// <summary>
    /// Get stem analysis statistics
    /// </summary>
    [HttpGet("statistics")]
    public async Task<ActionResult<StemStatisticsDto>> GetStemStatistics()
    {
        var totalStems = await _dbContext.Stems.CountAsync();
        var analyzedStems = await _dbContext.Stems.CountAsync(s => s.AnalysisStatus == StemAnalysisStatus.Completed);
        var pendingAnalysis = await _dbContext.Stems.CountAsync(s => s.AnalysisStatus == StemAnalysisStatus.Pending);
        var failedAnalysis = await _dbContext.Stems.CountAsync(s => s.AnalysisStatus == StemAnalysisStatus.Failed);

        var stemsByType = await _dbContext.Stems
            .GroupBy(s => s.Type)
            .Select(g => new { Type = g.Key, Count = g.Count() })
            .ToListAsync();

        var keyDistribution = await _dbContext.Stems
            .Where(s => s.Key != null && s.AnalysisStatus == StemAnalysisStatus.Completed)
            .GroupBy(s => s.Key)
            .Select(g => new { Key = g.Key, Count = g.Count() })
            .OrderByDescending(x => x.Count)
            .Take(10)
            .ToListAsync();

        return Ok(new StemStatisticsDto
        {
            TotalStems = totalStems,
            AnalyzedStems = analyzedStems,
            PendingAnalysis = pendingAnalysis,
            FailedAnalysis = failedAnalysis,
            StemsByType = stemsByType.ToDictionary(x => x.Type.ToString(), x => x.Count),
            TopKeys = keyDistribution.ToDictionary(x => x.Key!, x => x.Count)
        });
    }
}

// DTOs for request/response
public record StemDto
{
    public Guid Id { get; init; }
    public Guid AudioFileId { get; init; }
    public string Type { get; init; } = string.Empty;
    public string BlobUri { get; init; } = string.Empty;
    public float DurationSeconds { get; init; }
    public long FileSizeBytes { get; init; }
    public DateTime SeparatedAt { get; init; }
    public string SourceSeparationModel { get; init; } = string.Empty;
    
    // Musical metadata
    public double? Bpm { get; init; }
    public string? Key { get; init; }
    public string? TimeSignature { get; init; }
    public double? TuningFrequency { get; init; }
    
    // Audio quality metrics
    public double? RmsLevel { get; init; }
    public double? PeakLevel { get; init; }
    public double? SpectralCentroid { get; init; }
    public double? ZeroCrossingRate { get; init; }
    
    // Musical structure (JSON strings)
    public string? ChordProgression { get; init; }
    public string? Beats { get; init; }
    public string? Sections { get; init; }
    public string? NotationData { get; init; }
    public string? FlamingoInsightsJson { get; init; }
    
    // JAMS annotation
    public string? JamsUri { get; init; }
    
    // Analysis tracking
    public string AnalysisStatus { get; init; } = string.Empty;
    public string? AnalysisErrorMessage { get; init; }
    public DateTime? AnalyzedAt { get; init; }
    
    // Audio file metadata for display
    public string? AudioFileTitle { get; init; }
    public string? AudioFileArtist { get; init; }
    public string? AudioFileAlbum { get; init; }
    public string? AlbumArtworkUri { get; init; }

    public static StemDto FromStem(Stem stem) => new()
    {
        Id = stem.Id,
        AudioFileId = stem.AudioFileId,
        Type = stem.Type.ToString(),
        BlobUri = stem.BlobUri,
        DurationSeconds = stem.DurationSeconds,
        FileSizeBytes = stem.FileSizeBytes,
        SeparatedAt = stem.SeparatedAt,
        SourceSeparationModel = stem.SourceSeparationModel,
        Bpm = stem.Bpm,
        Key = stem.Key,
        TimeSignature = stem.TimeSignature,
        TuningFrequency = stem.TuningFrequency,
        RmsLevel = stem.RmsLevel,
        PeakLevel = stem.PeakLevel,
        SpectralCentroid = stem.SpectralCentroid,
        ZeroCrossingRate = stem.ZeroCrossingRate,
        ChordProgression = stem.ChordProgression,
        Beats = stem.Beats,
        Sections = stem.Sections,
    NotationData = stem.NotationData,
    FlamingoInsightsJson = stem.FlamingoInsightsJson,
        JamsUri = stem.JamsUri,
        AnalysisStatus = stem.AnalysisStatus.ToString(),
        AnalysisErrorMessage = stem.AnalysisErrorMessage,
        AnalyzedAt = stem.AnalyzedAt,
        // Audio file metadata
        AudioFileTitle = stem.AudioFile?.Title,
        AudioFileArtist = stem.AudioFile?.Artist,
        AudioFileAlbum = stem.AudioFile?.Album,
        AlbumArtworkUri = stem.AudioFile?.AlbumArtworkUri
    };
}

public record CreateStemRequest
{
    public Guid AudioFileId { get; init; }
    public StemType Type { get; init; }
    public string BlobUri { get; init; } = string.Empty;
    public float DurationSeconds { get; init; }
    public long FileSizeBytes { get; init; }
    public string SourceSeparationModel { get; init; } = string.Empty;
    
    // Optional musical metadata (can be populated later)
    public double? Bpm { get; init; }
    public string? Key { get; init; }
    public string? TimeSignature { get; init; }
    public double? TuningFrequency { get; init; }
    public double? RmsLevel { get; init; }
    public double? PeakLevel { get; init; }
    public double? SpectralCentroid { get; init; }
    public double? ZeroCrossingRate { get; init; }
    public string? ChordProgression { get; init; }
    public string? Beats { get; init; }
    public string? Sections { get; init; }
    public string? NotationData { get; init; }
    public string? FlamingoInsightsJson { get; init; }
    public string? JamsUri { get; init; }
    public StemAnalysisStatus? AnalysisStatus { get; init; }
    public string? AnalysisErrorMessage { get; init; }
    public DateTime? AnalyzedAt { get; init; }
}

public record UpdateStemAnalysisRequest
{
    public double? Bpm { get; init; }
    public string? Key { get; init; }
    public string? TimeSignature { get; init; }
    public double? TuningFrequency { get; init; }
    public double? RmsLevel { get; init; }
    public double? PeakLevel { get; init; }
    public double? SpectralCentroid { get; init; }
    public double? ZeroCrossingRate { get; init; }
    public string? ChordProgression { get; init; }
    public string? Beats { get; init; }
    public string? Sections { get; init; }
    public string? NotationData { get; init; }
    public string? FlamingoInsightsJson { get; init; }
    public string? JamsUri { get; init; }
    public StemAnalysisStatus AnalysisStatus { get; init; }
    public string? AnalysisErrorMessage { get; init; }
}

public record StemStatisticsDto
{
    public int TotalStems { get; init; }
    public int AnalyzedStems { get; init; }
    public int PendingAnalysis { get; init; }
    public int FailedAnalysis { get; init; }
    public Dictionary<string, int> StemsByType { get; init; } = new();
    public Dictionary<string, int> TopKeys { get; init; } = new();
}