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
        // Azure Container Apps deployment (dev environment)
        return "https://api-mo6rlbmgpkrs4.livelymushroom-0aa872a5.eastus2.azurecontainerapps.io";
        
        // Uncomment below to use local development:
        // return "http://localhost:5000";
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
