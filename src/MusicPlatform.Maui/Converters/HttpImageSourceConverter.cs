using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace MusicPlatform.Maui.Converters;

/// <summary>
/// Converts HTTP URL strings to ImageSource by downloading and caching locally
/// </summary>
public class HttpImageSourceConverter : IValueConverter
{
    private static readonly HttpClient _httpClient = new();
    private static readonly string _cacheDirectory;
    
    static HttpImageSourceConverter()
    {
        _cacheDirectory = Path.Combine(FileSystem.CacheDirectory, "images");
        Directory.CreateDirectory(_cacheDirectory);
        Console.WriteLine($"📁 Image cache directory: {_cacheDirectory}");
    }

    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is string urlString && !string.IsNullOrWhiteSpace(urlString))
        {
            try
            {
                // Download and cache the image synchronously (MAUI converters must be sync)
                var cachedFilePath = DownloadAndCacheImage(urlString);
                if (cachedFilePath != null && File.Exists(cachedFilePath))
                {
                    Console.WriteLine($"✅ Returning FileImageSource: {cachedFilePath}");
                    return ImageSource.FromFile(cachedFilePath);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Error creating ImageSource from URL {urlString}: {ex.Message}");
            }
        }
        
        return null;
    }

    private static string? DownloadAndCacheImage(string url)
    {
        try
        {
            // Create cache filename from URL hash
            var hash = ComputeHash(url);
            var extension = ".jpg";
            var cachedFile = Path.Combine(_cacheDirectory, $"{hash}{extension}");

            // Return cached file if exists
            if (File.Exists(cachedFile))
            {
                Console.WriteLine($"✅ Using cached image: {cachedFile}");
                return cachedFile;
            }

            // Download image synchronously
            Console.WriteLine($"📥 Downloading image from: {url}");
            var response = _httpClient.GetAsync(url).GetAwaiter().GetResult();
            response.EnsureSuccessStatusCode();

            // Save to cache
            var imageBytes = response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
            File.WriteAllBytes(cachedFile, imageBytes);
            
            Console.WriteLine($"✅ Cached image to: {cachedFile} ({imageBytes.Length} bytes)");
            return cachedFile;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Error downloading/caching image: {ex.Message}");
            return null;
        }
    }

    private static string ComputeHash(string input)
    {
        var bytes = Encoding.UTF8.GetBytes(input);
        var hash = MD5.HashData(bytes);
        return BitConverter.ToString(hash).Replace("-", "").ToLower();
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}
