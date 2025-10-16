using System.Net.Http.Json;
using System.Net.Http.Headers;

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
        return await _httpClient.GetFromJsonAsync<List<GenerationRequestDto>>(
            "/api/generation",
            cancellationToken
        );
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

    /// <summary>
    /// Downloads a generated stem
    /// </summary>
    public async Task<Stream?> DownloadStemAsync(
        Guid stemId,
        CancellationToken cancellationToken = default
    )
    {
        var response = await _httpClient.GetAsync(
            $"/api/generation/stems/{stemId}/download",
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken
        );

        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    #endregion

    #region Jobs Endpoints

    /// <summary>
    /// Gets job status by ID
    /// </summary>
    public async Task<JobStatusDto?> GetJobStatusAsync(
        Guid jobId,
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<JobStatusDto>(
            $"/api/jobs/{jobId}",
            cancellationToken
        );
    }

    /// <summary>
    /// Gets all jobs
    /// </summary>
    public async Task<List<JobStatusDto>?> GetAllJobsAsync(
        CancellationToken cancellationToken = default
    )
    {
        return await _httpClient.GetFromJsonAsync<List<JobStatusDto>>(
            "/api/jobs",
            cancellationToken
        );
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
    string? UserId
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
    DateTime CreatedAt
);

/// <summary>
/// Generation request creation data transfer object
/// </summary>
public record CreateGenerationRequestDto(
    Guid AudioFileId,
    string[] TargetStems,
    Dictionary<string, object>? Parameters = null
);

/// <summary>
/// Generation request data transfer object
/// </summary>
public record GenerationRequestDto(
    Guid Id,
    Guid AudioFileId,
    string[] TargetStems,
    string Parameters,
    string Status,
    DateTime CreatedAt,
    DateTime? CompletedAt
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
    DateTime CreatedAt
);

/// <summary>
/// Job status data transfer object
/// </summary>
public record JobStatusDto(
    Guid Id,
    string JobType,
    string Status,
    string? ErrorMessage,
    DateTime CreatedAt,
    DateTime? CompletedAt
);

#endregion
