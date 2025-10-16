using System.Net.Http.Json;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MusicPlatform.Maui.Services;

/// <summary>
/// HTTP client service for Music Platform API communication
/// </summary>
public class MusicPlatformApiClient
{
    private readonly HttpClient _httpClient;
    private readonly ApiSettings _settings;

    public MusicPlatformApiClient(HttpClient httpClient, ApiSettings settings)
    {
        _httpClient = httpClient;
        _settings = settings;

        // Configure HTTP client
        _httpClient.BaseAddress = new Uri(_settings.BaseUrl);
        _httpClient.Timeout = TimeSpan.FromSeconds(_settings.TimeoutSeconds);
        _httpClient.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/json")
        );
    }

    #region Audio Endpoints

    /// <summary>
    /// Uploads an audio file for processing
    /// </summary>
    public async Task<AudioFileDto?> UploadAudioAsync(
        Stream audioStream,
        string fileName,
        IProgress<double>? progress = null,
        CancellationToken cancellationToken = default
    )
    {
        using var content = new MultipartFormDataContent();
        var streamContent = new StreamContent(audioStream);
        streamContent.Headers.ContentType = new MediaTypeHeaderValue("audio/mpeg");
        content.Add(streamContent, "file", fileName);

        var response = await _httpClient.PostAsync(
            "/api/audio/upload",
            content,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<AudioFileDto>(cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Gets audio file metadata by ID
    /// </summary>
    public async Task<AudioFileDto?> GetAudioFileAsync(
        Guid audioFileId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<AudioFileDto>(
            $"/api/audio/{audioFileId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Gets all audio files
    /// </summary>
    public async Task<List<AudioFileDto>?> GetAllAudioFilesAsync(
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<List<AudioFileDto>>(
            "/api/audio",
            cancellationToken
        );
    }

    /// <summary>
    /// Downloads audio file content
    /// </summary>
    public async Task<Stream?> DownloadAudioAsync(
        Guid audioFileId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.GetAsync(
            $"/api/audio/{audioFileId}/download",
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    #endregion

    #region Analysis Endpoints

    /// <summary>
    /// Gets analysis results for an audio file
    /// </summary>
    public async Task<AnalysisResultDto?> GetAnalysisAsync(
        Guid audioFileId,
        CancellationToken cancellationToken = default
    )
    {
        try
        {
            var response = await _httpClient.GetAsync(
                $"/api/audio/{audioFileId}/analysis",
                cancellationToken
            );

            if (!response.IsSuccessStatusCode)
                return null;

            return await response.Content.ReadFromJsonAsync<AnalysisResultDto>(cancellationToken);
        }
        catch
        {
            // Return null if analysis doesn't exist yet
            return null;
        }
    }

    /// <summary>
    /// Requests analysis for an audio file
    /// </summary>
    public async Task<AnalysisResultDto?> RequestAnalysisAsync(
        Guid audioFileId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.PostAsync(
            $"/api/audio/{audioFileId}/analyze",
            null,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<AnalysisResultDto>(cancellationToken: cancellationToken);
    }

    #endregion

    #region Stems Endpoints

    /// <summary>
    /// Gets all stems for a specific audio file
    /// </summary>
    public async Task<List<StemDto>?> GetStemsByAudioFileAsync(
        Guid audioFileId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<List<StemDto>>(
            $"/api/audio/{audioFileId}/stems",
            cancellationToken
        );
    }
    
    /// <summary>
    /// Gets a single stem by ID with full details (including notation, chords, etc.)
    /// </summary>
    public async Task<StemDto?> GetStemByIdAsync(
        Guid stemId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<StemDto>(
            $"/api/stems/{stemId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Downloads a stem file
    /// </summary>
    public async Task<Stream?> DownloadStemAsync(
        Guid stemId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.GetAsync(
            $"/api/stems/{stemId}/download",
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    #endregion

    #region Generation Endpoints

    /// <summary>
    /// Creates a new generation request
    /// </summary>
    public async Task<GenerationRequestDto?> CreateGenerationRequestAsync(
        CreateGenerationRequestDto request,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.PostAsJsonAsync(
            "/api/generation",
            request,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<GenerationRequestDto>(cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Gets generation request by ID
    /// </summary>
    public async Task<GenerationRequestDto?> GetGenerationRequestAsync(
        Guid generationRequestId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<GenerationRequestDto>(
            $"/api/generation/{generationRequestId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Gets all generation requests
    /// </summary>
    public async Task<List<GenerationRequestDto>?> GetAllGenerationRequestsAsync(
        CancellationToken cancellationToken = default
    )
    {
        try
        {
            var response = await _httpClient.GetAsync("/api/generation", cancellationToken);
            response.EnsureSuccessStatusCode();
            
            var content = await response.Content.ReadAsStringAsync(cancellationToken);
            
            // Use custom JSON options that are more lenient
            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
                // This will skip properties that fail to deserialize
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            };
            
            return JsonSerializer.Deserialize<List<GenerationRequestDto>>(content, options);
        }
        catch (Exception)
        {
            // Return empty list instead of throwing
            return new List<GenerationRequestDto>();
        }
    }

    /// <summary>
    /// Gets all stems for a generation request
    /// </summary>
    public async Task<List<GeneratedStemDto>?> GetGeneratedStemsAsync(
        Guid generationRequestId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<List<GeneratedStemDto>>(
            $"/api/generation/{generationRequestId}/stems",
            cancellationToken
        );
    }

    #endregion

    #region Jobs Endpoints

    /// <summary>
    /// Gets job status by ID
    /// </summary>
    public async Task<JobDto?> GetJobAsync(
        Guid jobId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<JobDto>(
            $"/api/jobs/{jobId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Gets all jobs for a specific entity (audio file or generation request)
    /// </summary>
    public async Task<List<JobDto>?> GetJobsByEntityAsync(
        Guid entityId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<List<JobDto>>(
            $"/api/jobs/entity/{entityId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Gets all jobs with optional filtering
    /// </summary>
    public async Task<List<JobDto>?> GetAllJobsAsync(
        string? status = null,
        string? type = null,
        int skip = 0,
        int take = 20,
        CancellationToken cancellationToken = default
    )
    {
        var query = $"/api/jobs?skip={skip}&take={take}";
        if (!string.IsNullOrEmpty(status)) query += $"&status={status}";
        if (!string.IsNullOrEmpty(type)) query += $"&type={type}";
        
        return await _httpClient.GetFromJsonAsync<List<JobDto>>(
            query,
            cancellationToken
        );
    }

    /// <summary>
    /// Gets job statistics
    /// </summary>
    public async Task<JobStatisticsDto?> GetJobStatisticsAsync(
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<JobStatisticsDto>(
            "/api/jobs/stats",
            cancellationToken
        );
    }

    /// <summary>
    /// Cancels a running job
    /// </summary>
    public async Task<JobDto?> CancelJobAsync(
        Guid jobId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.PostAsync(
            $"/api/jobs/{jobId}/cancel",
            null,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JobDto>(cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Retries a failed job
    /// </summary>
    public async Task<JobDto?> RetryJobAsync(
        Guid jobId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.PostAsync(
            $"/api/jobs/{jobId}/retry",
            null,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JobDto>(cancellationToken: cancellationToken);
    }

    #endregion
}

#region DTOs

/// <summary>
/// Audio file data transfer object
/// </summary>
public record AudioFileDto(
    Guid Id,
    string OriginalFileName,
    long SizeBytes,
    string BlobUri,
    TimeSpan Duration,
    string Format,
    DateTime UploadedAt,
    string Status,
    string? UserId,
    // MP3 Metadata
    string? Title = null,
    string? Artist = null,
    string? Album = null,
    string? AlbumArtist = null,
    string? Year = null,
    string? Genre = null,
    string? TrackNumber = null,
    string? AlbumArtworkUri = null,
    // Technical Properties
    int? Bitrate = null,
    int? SampleRate = null,
    int? Channels = null,
    // Musical Analysis Results (from analysis worker)
    double? Bpm = null,
    string? Key = null,
    string? TimeSignature = null
);

/// <summary>
/// Analysis result data transfer object
/// </summary>
public record AnalysisResultDto(
    Guid Id,
    Guid AudioFileId,
    string Status,
    double? Bpm,
    string? Key,
    string? TimeSignature,
    string? Tuning,
    string? JamsData,
    DateTime? AnalyzedAt,
    DateTime CreatedAt,
    List<ChordAnnotationDto>? Chords = null
);

/// <summary>
/// Chord annotation data transfer object
/// </summary>
public record ChordAnnotationDto(
    float StartTime,
    float EndTime,
    string Chord,
    float Confidence
);

/// <summary>
/// Generation request creation data transfer object
/// </summary>
public record CreateGenerationRequestDto(
    Guid AudioFileId,
    string[] TargetStems,
    object? Parameters = null  // Changed from Dictionary<string, object>? to object? to allow any serializable structure
);

/// <summary>
/// Generation request data transfer object
/// </summary>
public record GenerationRequestDto(
    Guid Id,
    Guid AudioFileId,
    string[] TargetStems,
    GenerationParametersDto? Parameters,  // Changed from string? to object to match API
    string Status,
    DateTime CreatedAt,
    DateTime? CompletedAt
);

/// <summary>
/// Generation parameters data transfer object
/// </summary>
public record GenerationParametersDto(
    double? TargetBpm,
    double? DurationSeconds,
    string? Style,
    List<string>? ChordProgression,
    string? Prompt,
    double? Temperature,
    int? RandomSeed
);

/// <summary>
/// Generated stem data transfer object
/// </summary>
public record GeneratedStemDto(
    Guid Id,
    Guid GenerationRequestId,
    string StemType,
    string BlobPath,
    long FileSizeBytes,
    double? DurationSeconds,
    string? Metadata,
    DateTime CreatedAt,
    // Audio File metadata for display
    Guid? AudioFileId = null,
    string? AudioFileTitle = null,
    string? AudioFileArtist = null,
    string? AudioFileAlbum = null,
    string? AlbumArtworkUri = null
);

/// <summary>
/// Stem data transfer object from Stems controller
/// </summary>
public record StemDto(
    Guid Id,
    Guid AudioFileId,
    string Type,
    string BlobUri,
    float DurationSeconds,
    long FileSizeBytes,
    DateTime SeparatedAt,
    string SourceSeparationModel,
    double? Bpm = null,
    string? Key = null,
    string? TimeSignature = null,
    double? TuningFrequency = null,
    double? RmsLevel = null,
    double? PeakLevel = null,
    double? SpectralCentroid = null,
    double? ZeroCrossingRate = null,
    string? ChordProgression = null,
    string? Beats = null,
    string? Sections = null,
    string? NotationData = null,
    string? JamsUri = null,
    string AnalysisStatus = "Pending",
    string? AnalysisErrorMessage = null,
    DateTime? AnalyzedAt = null
);

/// <summary>
/// Job data transfer object with enhanced idempotent features
/// </summary>
public record JobDto(
    Guid Id,
    string Type,
    Guid EntityId,
    string OrchestrationInstanceId,
    string Status,
    DateTime StartedAt,
    DateTime? CompletedAt,
    DateTime? LastHeartbeat,
    string? ErrorMessage,
    Dictionary<string, object>? Metadata,
    string? IdempotencyKey,
    int RetryCount,
    int MaxRetries,
    string? WorkerInstanceId,
    string? CurrentStep,
    Dictionary<string, object>? Checkpoints
);

/// <summary>
/// Job statistics data transfer object
/// </summary>
public record JobStatisticsDto(
    int TotalJobs,
    int PendingJobs,
    int RunningJobs,
    int CompletedJobs,
    int FailedJobs,
    int CancelledJobs,
    int AnalysisJobs,
    int GenerationJobs,
    double AverageCompletionTimeSeconds
);

#endregion
