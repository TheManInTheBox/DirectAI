using System.Text.Json;

namespace MusicPlatform.WinUI.Services;

public static class Config
{
    private static string? _cachedBaseUrl;

    public static string ResolveBaseApiUrl()
    {
        if (_cachedBaseUrl != null)
        {
            return _cachedBaseUrl;
        }

        // 1) Try appsettings.json first
        var appSettingsPath = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
        if (File.Exists(appSettingsPath))
        {
            try
            {
                var json = File.ReadAllText(appSettingsPath);
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("ApiSettings", out var apiSettings) &&
                    apiSettings.TryGetProperty("BaseUrl", out var baseUrl))
                {
                    var url = baseUrl.GetString();
                    if (!string.IsNullOrWhiteSpace(url))
                    {
                        _cachedBaseUrl = TrimTrailingSlash(url);
                        return _cachedBaseUrl;
                    }
                }
            }
            catch { /* ignore and fall back */ }
        }

        // 2) .azure/dev/.env (for Azure deployment)
        var envPath = FindFileUpwards(".azure\\dev\\.env");
        if (envPath != null && File.Exists(envPath))
        {
            try
            {
                foreach (var line in File.ReadAllLines(envPath))
                {
                    if (line.TrimStart().StartsWith("API_ENDPOINT", StringComparison.OrdinalIgnoreCase))
                    {
                        var idx = line.IndexOf('=');
                        if (idx > 0)
                        {
                            var raw = line[(idx + 1)..].Trim().Trim('"');
                            if (!string.IsNullOrWhiteSpace(raw))
                            {
                                _cachedBaseUrl = TrimTrailingSlash(raw);
                                return _cachedBaseUrl;
                            }
                        }
                    }
                }
            }
            catch { /* ignore and fall back */ }
        }

        // 3) Default to local dev
        _cachedBaseUrl = "http://localhost:5000";
        return _cachedBaseUrl;
    }

    private static string TrimTrailingSlash(string url)
    {
        return url.EndsWith('/') ? url.TrimEnd('/') : url;
    }

    private static string? FindFileUpwards(string relativePath)
    {
        try
        {
            var dir = AppContext.BaseDirectory;
            while (!string.IsNullOrEmpty(dir))
            {
                var candidate = Path.Combine(dir, relativePath);
                if (File.Exists(candidate)) return candidate;
                var parent = Directory.GetParent(dir);
                if (parent == null) break;
                dir = parent.FullName;
            }
        }
        catch { }
        return null;
    }
}
