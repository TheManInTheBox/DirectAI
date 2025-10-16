using System.Security.Cryptography;
using System.Text;

namespace MusicPlatform.Maui.Services;

/// <summary>
/// Service to download and cache images locally for display
/// </summary>
public class ImageCacheService
{
    private readonly HttpClient _httpClient;
    private readonly string _cacheDirectory;

    public ImageCacheService(HttpClient httpClient)
    {
        _httpClient = httpClient;
        _cacheDirectory = Path.Combine(FileSystem.CacheDirectory, "images");
        Directory.CreateDirectory(_cacheDirectory);
    }

    /// <summary>
    /// Downloads an image from URL and returns local file path
    /// </summary>
    public async Task<string?> GetImageAsync(string? url)
    {
        if (string.IsNullOrWhiteSpace(url))
            return null;

        try
        {
            // Create cache filename from URL hash
            var hash = ComputeHash(url);
            var extension = Path.GetExtension(url) ?? ".jpg";
            var cachedFile = Path.Combine(_cacheDirectory, $"{hash}{extension}");

            // Return cached file if exists
            if (File.Exists(cachedFile))
            {
                Console.WriteLine($"✅ Using cached image: {cachedFile}");
                return cachedFile;
            }

            // Download image
            Console.WriteLine($"📥 Downloading image from: {url}");
            var response = await _httpClient.GetAsync(url);
            response.EnsureSuccessStatusCode();

            // Save to cache
            var imageBytes = await response.Content.ReadAsByteArrayAsync();
            await File.WriteAllBytesAsync(cachedFile, imageBytes);
            
            Console.WriteLine($"✅ Cached image to: {cachedFile} ({imageBytes.Length} bytes)");
            return cachedFile;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Error downloading image from {url}: {ex.Message}");
            return null;
        }
    }

    private static string ComputeHash(string input)
    {
        var bytes = Encoding.UTF8.GetBytes(input);
        var hash = MD5.HashData(bytes);
        return Convert.ToHexString(hash).ToLower();
    }
}
