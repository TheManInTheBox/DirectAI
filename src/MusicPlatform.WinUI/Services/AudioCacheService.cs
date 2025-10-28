using Windows.Storage;
using System.Security.Cryptography;
using System.Text;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// Local audio file caching service for improved performance
/// </summary>
public class AudioCacheService
{
    private const long MaxCacheSizeBytes = 500 * 1024 * 1024; // 500 MB
    private StorageFolder? _cacheFolder;
    private readonly Dictionary<string, CacheEntry> _cacheIndex = new();
    private readonly SemaphoreSlim _cacheLock = new(1, 1);
    private Task? _initializationTask;

    public AudioCacheService()
    {
        // Start initialization asynchronously without blocking constructor
        _initializationTask = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        try
        {
            var localCacheFolder = ApplicationData.Current.LocalCacheFolder;
            _cacheFolder = await localCacheFolder.CreateFolderAsync("AudioCache", CreationCollisionOption.OpenIfExists);
            await InitializeCacheIndexAsync();
        }
        catch
        {
            // Silently fail initialization - cache will be disabled
        }
    }

    private async Task InitializeCacheIndexAsync()
    {
        await _cacheLock.WaitAsync();
        try
        {
            if (_cacheFolder == null) return;
            
            var files = await _cacheFolder.GetFilesAsync();
            foreach (var file in files)
            {
                var props = await file.GetBasicPropertiesAsync();
                _cacheIndex[file.Name] = new CacheEntry
                {
                    FileName = file.Name,
                    Size = (long)props.Size,
                    LastAccessed = props.DateModified.DateTime
                };
            }
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    public async Task<StorageFile?> GetCachedAudioAsync(string cacheKey)
    {
        if (_initializationTask != null) await _initializationTask;
        if (_cacheFolder == null) return null;
        
        await _cacheLock.WaitAsync();
        try
        {
            var fileName = GetCacheFileName(cacheKey);
            if (_cacheIndex.ContainsKey(fileName))
            {
                var file = await _cacheFolder.TryGetItemAsync(fileName) as StorageFile;
                if (file != null)
                {
                    // Update last accessed time
                    _cacheIndex[fileName].LastAccessed = DateTime.UtcNow;
                    return file;
                }
                else
                {
                    // File was deleted externally
                    _cacheIndex.Remove(fileName);
                }
            }
            return null;
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    public async Task<StorageFile> CacheAudioAsync(string cacheKey, Stream audioStream, string originalFileName)
    {
        if (_initializationTask != null) await _initializationTask;
        if (_cacheFolder == null) throw new InvalidOperationException("Cache not initialized");
        
        await _cacheLock.WaitAsync();
        try
        {
            var fileName = GetCacheFileName(cacheKey);
            var extension = Path.GetExtension(originalFileName);
            var cacheFileName = fileName + extension;

            // Check if we need to evict old files
            var streamLength = audioStream.CanSeek ? audioStream.Length : 0;
            await EvictIfNeededAsync(streamLength);

            // Create cache file
            var file = await _cacheFolder.CreateFileAsync(cacheFileName, CreationCollisionOption.ReplaceExisting);
            
            using (var fileStream = await file.OpenStreamForWriteAsync())
            {
                await audioStream.CopyToAsync(fileStream);
            }

            // Update cache index
            var props = await file.GetBasicPropertiesAsync();
            _cacheIndex[cacheFileName] = new CacheEntry
            {
                FileName = cacheFileName,
                Size = (long)props.Size,
                LastAccessed = DateTime.UtcNow
            };

            return file;
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    public async Task<StorageFile> GetOrCacheAudioAsync(string cacheKey, Func<Task<Stream>> audioStreamFactory, string originalFileName)
    {
        // Try to get from cache first
        var cachedFile = await GetCachedAudioAsync(cacheKey);
        if (cachedFile != null)
        {
            return cachedFile;
        }

        // Download and cache
        var stream = await audioStreamFactory();
        return await CacheAudioAsync(cacheKey, stream, originalFileName);
    }

    private async Task EvictIfNeededAsync(long requiredSpace)
    {
        if (_cacheFolder == null) return;
        
        var currentSize = _cacheIndex.Values.Sum(e => e.Size);
        
        if (currentSize + requiredSpace <= MaxCacheSizeBytes)
        {
            return;
        }

        // Evict least recently used files
        var entriesToEvict = _cacheIndex.Values
            .OrderBy(e => e.LastAccessed)
            .ToList();

        long freedSpace = 0;
        foreach (var entry in entriesToEvict)
        {
            if (currentSize - freedSpace + requiredSpace <= MaxCacheSizeBytes * 0.8) // Keep 20% buffer
            {
                break;
            }

            try
            {
                var file = await _cacheFolder.GetFileAsync(entry.FileName);
                await file.DeleteAsync();
                _cacheIndex.Remove(entry.FileName);
                freedSpace += entry.Size;
            }
            catch
            {
                // File might already be deleted
                _cacheIndex.Remove(entry.FileName);
            }
        }
    }

    public async Task ClearCacheAsync()
    {
        if (_initializationTask != null) await _initializationTask;
        if (_cacheFolder == null) return;
        
        await _cacheLock.WaitAsync();
        try
        {
            var files = await _cacheFolder.GetFilesAsync();
            foreach (var file in files)
            {
                await file.DeleteAsync();
            }
            _cacheIndex.Clear();
        }
        finally
        {
            _cacheLock.Release();
        }
    }

    public long GetCacheSize()
    {
        return _cacheIndex.Values.Sum(e => e.Size);
    }

    public int GetCachedFileCount()
    {
        return _cacheIndex.Count;
    }

    private static string GetCacheFileName(string cacheKey)
    {
        // Create hash of cache key for filename
        using var sha256 = SHA256.Create();
        var hashBytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(cacheKey));
        return Convert.ToHexString(hashBytes);
    }

    private class CacheEntry
    {
        public required string FileName { get; set; }
        public long Size { get; set; }
        public DateTime LastAccessed { get; set; }
    }
}
