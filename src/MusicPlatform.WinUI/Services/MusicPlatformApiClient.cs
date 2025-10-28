using System.Net.Http.Json;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;
using MusicPlatform.WinUI.Models;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// HTTP client service for Music Platform API communication
/// </summary>
public class MusicPlatformApiClient
{
    private readonly HttpClient _httpClient;

    public MusicPlatformApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    #region Audio Endpoints

    public async Task<AudioFileDto?> UploadAudioAsync(
        Stream audioStream,
        string fileName,
        IProgress<double>? progress = null,
        CancellationToken cancellationToken = default)
    {
        using var content = new MultipartFormDataContent();
        var streamContent = new StreamContent(audioStream);
        streamContent.Headers.ContentType = new MediaTypeHeaderValue("audio/mpeg");
        content.Add(streamContent, "file", fileName);

        var response = await _httpClient.PostAsync("/api/audio/upload", content, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<AudioFileDto>(cancellationToken: cancellationToken);
    }

    public async Task<AudioFileDto?> GetAudioFileAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<AudioFileDto>($"/api/audio/{audioFileId}", cancellationToken);
    }

    public async Task<List<AudioFileDto>?> GetAllAudioFilesAsync(CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<List<AudioFileDto>>("/api/audio", cancellationToken);
    }

    public async Task<Stream?> DownloadAudioAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/audio/{audioFileId}/download", HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    public async Task DeleteAudioFileAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync($"/api/audio/{audioFileId}", cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    #endregion

    #region Analysis Endpoints

    public async Task<AnalysisResultDto?> RequestAnalysisAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsync($"/api/audio/{audioFileId}/analyze", null, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<AnalysisResultDto>(cancellationToken: cancellationToken);
    }

    public async Task<AnalysisResultDto?> GetAnalysisAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<AnalysisResultDto>($"/api/audio/{audioFileId}/analysis", cancellationToken);
        }
        catch
        {
            return null;
        }
    }

    #endregion

    #region Stems Endpoints

    public async Task<List<StemDto>?> GetStemsByAudioFileAsync(Guid audioFileId, CancellationToken cancellationToken = default)
    {
        // Match server route: StemsController [HttpGet("audio/{audioFileId}")]
        return await _httpClient.GetFromJsonAsync<List<StemDto>>($"/api/stems/audio/{audioFileId}", cancellationToken);
    }

    public async Task<StemDto?> GetStemByIdAsync(Guid stemId, CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<StemDto>($"/api/stems/{stemId}", cancellationToken);
    }

    public async Task<Stream?> DownloadStemAsync(Guid stemId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/stems/{stemId}/download", HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    public async Task<StemStatisticsDto?> GetStemStatisticsAsync(CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<StemStatisticsDto>("/api/stems/statistics", cancellationToken);
    }

    #endregion

    #region Generation Endpoints

    public async Task<GenerationRequestDto?> CreateGenerationRequestAsync(CreateGenerationRequestDto request, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.PostAsJsonAsync("/api/generation", request, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<GenerationRequestDto>(cancellationToken: cancellationToken);
    }

    public async Task<GenerationRequestDto?> GetGenerationRequestAsync(Guid generationRequestId, CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<GenerationRequestDto>($"/api/generation/{generationRequestId}", cancellationToken);
    }

    public async Task<List<GenerationRequestDto>?> GetAllGenerationRequestsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<List<GenerationRequestDto>>("/api/generation", cancellationToken);
        }
        catch
        {
            return new List<GenerationRequestDto>();
        }
    }

    public async Task<List<GeneratedStemDto>?> GetGeneratedStemsAsync(Guid generationRequestId, CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<List<GeneratedStemDto>>($"/api/generation/{generationRequestId}/stems", cancellationToken);
    }

    public async Task<Stream?> DownloadGeneratedStemAsync(Guid stemId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync($"/api/generation/download-stem/{stemId}", HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStreamAsync(cancellationToken);
    }

    #endregion

    #region Jobs Endpoints

    public async Task<JobDto?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default)
    {
        return await _httpClient.GetFromJsonAsync<JobDto>($"/api/jobs/{jobId}", cancellationToken);
    }

    public async Task<List<JobDto>?> GetAllJobsAsync(string? status = null, string? type = null, int skip = 0, int take = 20, CancellationToken cancellationToken = default)
    {
        var query = $"/api/jobs?skip={skip}&take={take}";
        if (!string.IsNullOrEmpty(status)) query += $"&status={status}";
        if (!string.IsNullOrEmpty(type)) query += $"&type={type}";
        
        return await _httpClient.GetFromJsonAsync<List<JobDto>>(query, cancellationToken);
    }

    #endregion
}
