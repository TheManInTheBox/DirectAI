using System.Text.Json;
using Windows.Storage;
using MusicPlatform.WinUI.Models;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// Persistent on-disk cache for audio library data
/// </summary>
public class AudioLibraryCacheService
{
    private const string CacheFileName = "audio_library_cache.json";
    private const string CacheMetadataFileName = "audio_library_cache_metadata.json";
    private StorageFolder? _cacheFolder;
    private readonly SemaphoreSlim _cacheLock = new(1, 1);

    public AudioLibraryCacheService()
    {
    }

    private async Task EnsureCacheFolderAsync()
    {
        if (_cacheFolder == null)
        {
            var localCacheFolder = ApplicationData.Current.LocalCacheFolder;
            _cacheFolder = await localCacheFolder.CreateFolderAsync("AudioLibraryCache", CreationCollisionOption.OpenIfExists);
        }
    }

    /// <summary>
    /// Save audio library data to disk cache
    /// </summary>
    public async Task SaveCacheAsync(IEnumerable<AudioFileDto> audioFiles, Dictionary<Guid, int> stemCounts)
    {
        await _cacheLock.WaitAsync();
        try
        {
            await EnsureCacheFolderAsync();

            var cacheData = new AudioLibraryCacheData
            {
                AudioFiles = audioFiles.ToList(),
                StemCounts = stemCounts,
                CachedAt = DateTime.UtcNow
            };

            var json = JsonSerializer.Serialize(cacheData, new JsonSerializerOptions
            {
                WriteIndented = true
            });

            var cacheFile = await _cacheFolder!.CreateFileAsync(CacheFileName, CreationCollisionOption.ReplaceExisting);
            await FileIO.WriteTextAsync(cacheFile, json);

            System.Diagnostics.Debug.WriteLine($"Audio library cache saved: {audioFiles.Count()} files");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error saving audio library cache: {ex.Message}");
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    /// <summary>
    /// Load audio library data from disk cache
    /// </summary>
    public async Task<AudioLibraryCacheData?> LoadCacheAsync()
    {
        await _cacheLock.WaitAsync();
        try
        {
            await EnsureCacheFolderAsync();

            var cacheFile = await _cacheFolder!.TryGetItemAsync(CacheFileName) as StorageFile;
            if (cacheFile == null)
            {
                System.Diagnostics.Debug.WriteLine("No audio library cache found");
                return null;
            }

            var json = await FileIO.ReadTextAsync(cacheFile);
            var cacheData = JsonSerializer.Deserialize<AudioLibraryCacheData>(json);

            if (cacheData != null)
            {
                System.Diagnostics.Debug.WriteLine($"Audio library cache loaded: {cacheData.AudioFiles.Count} files, cached at {cacheData.CachedAt}");
            }

            return cacheData;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error loading audio library cache: {ex.Message}");
            return null;
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    /// <summary>
    /// Clear the cache
    /// </summary>
    public async Task ClearCacheAsync()
    {
        await _cacheLock.WaitAsync();
        try
        {
            await EnsureCacheFolderAsync();

            var cacheFile = await _cacheFolder!.TryGetItemAsync(CacheFileName) as StorageFile;
            if (cacheFile != null)
            {
                await cacheFile.DeleteAsync();
                System.Diagnostics.Debug.WriteLine("Audio library cache cleared");
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error clearing audio library cache: {ex.Message}");
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    /// <summary>
    /// Check if cache exists and is recent (within 24 hours)
    /// </summary>
    public async Task<bool> IsCacheValidAsync()
    {
        var cache = await LoadCacheAsync();
        if (cache == null)
            return false;

        var age = DateTime.UtcNow - cache.CachedAt;
        return age.TotalHours < 24; // Cache is valid for 24 hours
    }
}

public class AudioLibraryCacheData
{
    public List<AudioFileDto> AudioFiles { get; set; } = new();
    public Dictionary<Guid, int> StemCounts { get; set; } = new();
    public DateTime CachedAt { get; set; }
}
