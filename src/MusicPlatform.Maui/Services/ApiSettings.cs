namespace MusicPlatform.Maui.Services;

/// <summary>
/// API configuration settings - automatically detects local vs Azure environment
/// </summary>
public class ApiSettings
{
    /// <summary>
    /// Base URL for the Music Platform API
    /// </summary>
    public string BaseUrl { get; set; } = GetDefaultBaseUrl();

    /// <summary>
    /// Timeout for API requests (in seconds)
    /// </summary>
    public int TimeoutSeconds { get; set; } = 300; // 5 minutes for file uploads

    /// <summary>
    /// Determines the default API base URL based on build configuration
    /// </summary>
    private static string GetDefaultBaseUrl()
    {
#if DEBUG
        // Local development - Docker Desktop
        return "http://localhost:5000";
#else
        // Production - Azure deployment
        // TODO: Replace with actual Azure App Service URL after deployment
        return "https://musicplatform-api.azurewebsites.net";
#endif
    }

    /// <summary>
    /// Gets the full URL for an API endpoint
    /// </summary>
    public string GetEndpoint(string path)
    {
        var baseUrl = BaseUrl.TrimEnd('/');
        var endpoint = path.TrimStart('/');
        return $"{baseUrl}/{endpoint}";
    }
}
