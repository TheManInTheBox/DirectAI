using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MusicPlatform.WinUI.Models;
using MusicPlatform.WinUI.Services;
using System.Collections.ObjectModel;
using System.Linq;
using Windows.Storage;

namespace MusicPlatform.WinUI.ViewModels;

public partial class MixingViewModel : ObservableObject
{
    private readonly MusicPlatformApiClient _apiClient;
    private readonly AudioPlaybackService _audioService;
    private readonly AudioCacheService _cacheService;
    private readonly AudioLibraryCacheService _libraryCacheService;
    private readonly WaveformService _waveformService;
    private readonly FastWaveformService _fastWaveformService;

    [ObservableProperty]
    private ObservableCollection<AudioFileItemViewModel> _availableAudioFiles = new();

    [ObservableProperty]
    private ObservableCollection<MixTrack> _tracks = new();

    [ObservableProperty]
    private bool _isPlaying;

    [ObservableProperty]
    private string _duration = "00:00.000";

    [ObservableProperty]
    private string _currentTime = "00:00";

    [ObservableProperty]
    private string _statusMessage = "Ready";

    [ObservableProperty]
    private double _playbackCursorPosition = 0; // 0-100% position for visual cursor

    public bool HasTracks => Tracks.Count > 0;

    public MixingViewModel(
        MusicPlatformApiClient apiClient, 
        AudioPlaybackService audioService,
        AudioCacheService cacheService,
        AudioLibraryCacheService libraryCacheService,
        WaveformService waveformService,
        FastWaveformService fastWaveformService)
    {
        _apiClient = apiClient;
        _audioService = audioService;
        _cacheService = cacheService;
        _libraryCacheService = libraryCacheService;
        _waveformService = waveformService;
        _fastWaveformService = fastWaveformService;

        LoadAudioFilesCommand = new AsyncRelayCommand(LoadAudioFilesAsync);

        // Subscribe to audio service events for timeline updates
        _audioService.PositionChanged += (sender, position) =>
        {
            var duration = _audioService.Duration;
            CurrentTime = $"{position.Minutes:D2}:{position.Seconds:D2}";
            
            // Update cursor position (0-100%)
            if (duration.TotalSeconds > 0)
            {
                PlaybackCursorPosition = (position.TotalSeconds / duration.TotalSeconds) * 100.0;
            }
        };

        _audioService.PlaybackStateChanged += (sender, args) =>
        {
            IsPlaying = args.State == Windows.Media.Playback.MediaPlaybackState.Playing;
        };
        
        // Generate waveforms for any existing tracks
        _ = Task.Run(async () => await RegenerateAllWaveformsAsync());
    }

    public IAsyncRelayCommand LoadAudioFilesCommand { get; }
    
    /// <summary>
    /// Regenerates waveforms for all existing tracks that have cached audio
    /// </summary>
    private async Task RegenerateAllWaveformsAsync()
    {
        if (!Tracks.Any()) return;
        
        System.Diagnostics.Debug.WriteLine($"=== REGENERATING WAVEFORMS FOR {Tracks.Count} EXISTING TRACKS ===");
        
        foreach (var track in Tracks)
        {
            try
            {
                // Try to find cached audio - look for stem cache key pattern
                var stemType = track.StemType ?? "vocals"; // Default guess
                var possibleCacheKeys = new[]
                {
                    $"stem_{track.Id}",
                    $"stem_{stemType}",
                    track.Name // Might be cached by name
                };
                
                StorageFile? cachedFile = null;
                string? usedCacheKey = null;
                
                foreach (var cacheKey in possibleCacheKeys)
                {
                    cachedFile = await _cacheService.GetCachedAudioAsync(cacheKey);
                    if (cachedFile != null)
                    {
                        usedCacheKey = cacheKey;
                        break;
                    }
                }
                
                if (cachedFile != null)
                {
                    System.Diagnostics.Debug.WriteLine($"Regenerating waveform for track: {track.Name} (cache key: {usedCacheKey})");
                    var waveform = await _fastWaveformService.GenerateWaveformFromAudioAsync(cachedFile, 800, 80);
                    
                    // Update on UI thread
                    Microsoft.UI.Dispatching.DispatcherQueue.GetForCurrentThread()?.TryEnqueue(() =>
                    {
                        track.WaveformPath = waveform;
                        System.Diagnostics.Debug.WriteLine($"✓ Waveform updated for {track.Name}");
                    });
                }
                else
                {
                    System.Diagnostics.Debug.WriteLine($"✗ No cached audio found for track: {track.Name}");
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error regenerating waveform for {track.Name}: {ex.Message}");
            }
        }
        
        System.Diagnostics.Debug.WriteLine("=== WAVEFORM REGENERATION COMPLETE ===");
    }

    /// <summary>
    /// Fully loads all audio files and stems data - used during startup to ensure complete loading
    /// </summary>
    public async Task LoadAudioFilesCompletelyAsync()
    {
        System.Diagnostics.Debug.WriteLine("MIXING: Loading audio files completely for mixing...");
        
        try
        {
            // First try to load from cache (should be populated during startup)
            System.Diagnostics.Debug.WriteLine("MIXING: Attempting to load from cache...");
            var cacheData = await _libraryCacheService.LoadCacheAsync();
            
            if (cacheData?.AudioFiles != null && cacheData.AudioFiles.Any())
            {
                System.Diagnostics.Debug.WriteLine($"MIXING: Found cache with {cacheData.AudioFiles.Count} files, cached at {cacheData.CachedAt}");
                
                // Load from cache with stem counts - this should be instant
                AvailableAudioFiles.Clear();
                foreach (var audioFile in cacheData.AudioFiles)
                {
                    var stemCount = cacheData.StemCounts.TryGetValue(audioFile.Id, out int count) ? count : 0;
                    AvailableAudioFiles.Add(new AudioFileItemViewModel
                    {
                        AudioFile = audioFile,
                        StemCount = stemCount,
                        HasStems = stemCount > 0 ? Microsoft.UI.Xaml.Visibility.Visible : Microsoft.UI.Xaml.Visibility.Collapsed
                    });
                }
                System.Diagnostics.Debug.WriteLine($"MIXING: Successfully loaded {AvailableAudioFiles.Count} files from cache");
                
                // Update UI to show loaded data immediately
                OnPropertyChanged(nameof(AvailableAudioFiles));
                
                // Check cache age - if recent, don't refresh from API
                var age = DateTime.UtcNow - cacheData.CachedAt;
                System.Diagnostics.Debug.WriteLine($"MIXING: Cache age: {age.TotalMinutes:F1} minutes");
                
                if (age.TotalMinutes < 10) // If cache is less than 10 minutes old, use it as-is
                {
                    System.Diagnostics.Debug.WriteLine("MIXING: Cache is recent, using cached data and skipping API refresh");
                    return;
                }
                else
                {
                    System.Diagnostics.Debug.WriteLine("MIXING: Cache is old, will refresh from API in background");
                    // Continue to API refresh below but data is already loaded from cache
                }
            }
            else
            {
                System.Diagnostics.Debug.WriteLine("MIXING: No cache found or cache is empty");
            }

            // Only reach here if no cache or cache is old - refresh from API
            System.Diagnostics.Debug.WriteLine("MIXING: Loading fresh data from API...");
            var audioFiles = await _apiClient.GetAllAudioFilesAsync();
            
            if (audioFiles != null && audioFiles.Any())
            {
                System.Diagnostics.Debug.WriteLine($"MIXING: Got {audioFiles.Count()} files from API, loading stem counts...");
                
                // Load stem counts concurrently
                var results = await Task.WhenAll(audioFiles.Select(async audioFile =>
                {
                    try
                    {
                        var stems = await _apiClient.GetStemsByAudioFileAsync(audioFile.Id);
                        var stemCount = stems?.Count() ?? 0;
                        return new { AudioFile = audioFile, StemCount = stemCount };
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"MIXING: Error loading stems for {audioFile.OriginalFileName}: {ex.Message}");
                        return new { AudioFile = audioFile, StemCount = 0 };
                    }
                }));

                // Update collection directly (works during startup before MainWindow exists)
                AvailableAudioFiles.Clear();
                foreach (var result in results)
                {
                    AvailableAudioFiles.Add(new AudioFileItemViewModel
                    {
                        AudioFile = result.AudioFile,
                        StemCount = result.StemCount,
                        HasStems = result.StemCount > 0 ? Microsoft.UI.Xaml.Visibility.Visible : Microsoft.UI.Xaml.Visibility.Collapsed
                    });
                }
                System.Diagnostics.Debug.WriteLine($"MIXING: Collection updated with {results.Length} items from API");
                OnPropertyChanged(nameof(AvailableAudioFiles));
                
                // Save refreshed data to cache
                var stemCounts = results.ToDictionary(r => r.AudioFile.Id, r => r.StemCount);
                await _libraryCacheService.SaveCacheAsync(audioFiles, stemCounts);
                System.Diagnostics.Debug.WriteLine("MIXING: Saved refreshed data to cache");
            }
            else
            {
                System.Diagnostics.Debug.WriteLine("MIXING: No audio files returned from API");
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"MIXING: Error loading audio files: {ex.Message}");
            App.MainWindow?.DispatcherQueue.TryEnqueue(() => StatusMessage = $"Error loading files: {ex.Message}");
        }
        
        System.Diagnostics.Debug.WriteLine($"MIXING: Audio files loading completed - Final count: {AvailableAudioFiles.Count}");
    }

    private async Task LoadAudioFilesAsync()
    {
        System.Diagnostics.Debug.WriteLine("NAVIGATION: Loading audio files for mixing...");
        
        try
        {
            // First check cache - this should be instant if populated during startup
            var cacheData = await _libraryCacheService.LoadCacheAsync();
            if (cacheData?.AudioFiles != null && cacheData.AudioFiles.Any())
            {
                System.Diagnostics.Debug.WriteLine($"NAVIGATION: Found {cacheData.AudioFiles.Count} items in cache, cached at {cacheData.CachedAt}");
                
                // Load from cache with stem counts for instant display
                AvailableAudioFiles.Clear();
                foreach (var audioFile in cacheData.AudioFiles)
                {
                    var stemCount = cacheData.StemCounts.TryGetValue(audioFile.Id, out int count) ? count : 0;
                    AvailableAudioFiles.Add(new AudioFileItemViewModel
                    {
                        AudioFile = audioFile,
                        StemCount = stemCount,
                        HasStems = stemCount > 0 ? Microsoft.UI.Xaml.Visibility.Visible : Microsoft.UI.Xaml.Visibility.Collapsed
                    });
                }
                
                System.Diagnostics.Debug.WriteLine($"NAVIGATION: Loaded {AvailableAudioFiles.Count} files from cache instantly");
                OnPropertyChanged(nameof(AvailableAudioFiles));
                
                // Check if cache is recent - if so, don't refresh
                var age = DateTime.UtcNow - cacheData.CachedAt;
                if (age.TotalMinutes < 15) // Cache valid for 15 minutes
                {
                    System.Diagnostics.Debug.WriteLine($"NAVIGATION: Cache is fresh ({age.TotalMinutes:F1} min), skipping API refresh");
                    return;
                }
                
                System.Diagnostics.Debug.WriteLine($"NAVIGATION: Cache is old ({age.TotalMinutes:F1} min), will refresh in background");
            }
            else
            {
                System.Diagnostics.Debug.WriteLine("NAVIGATION: No cache found, loading from API...");
            }

            // Only refresh from API if cache is old or missing
            // Do this in background so UI shows cached data immediately
            _ = Task.Run(async () =>
            {
                try
                {
                    System.Diagnostics.Debug.WriteLine("NAVIGATION: Refreshing from API in background...");
                    var audioFiles = await _apiClient.GetAllAudioFilesAsync();
                    
                    if (audioFiles != null && audioFiles.Any())
                    {
                        var results = await Task.WhenAll(audioFiles.Select(async audioFile =>
                        {
                            try
                            {
                                var stems = await _apiClient.GetStemsByAudioFileAsync(audioFile.Id);
                                var stemCount = stems?.Count() ?? 0;
                                return new { AudioFile = audioFile, StemCount = stemCount };
                            }
                            catch
                            {
                                return new { AudioFile = audioFile, StemCount = 0 };
                            }
                        }));

                        // Update UI on main thread
                        App.MainWindow?.DispatcherQueue.TryEnqueue(() =>
                        {
                            AvailableAudioFiles.Clear();
                            foreach (var result in results)
                            {
                                AvailableAudioFiles.Add(new AudioFileItemViewModel
                                {
                                    AudioFile = result.AudioFile,
                                    StemCount = result.StemCount,
                                    HasStems = result.StemCount > 0 ? Microsoft.UI.Xaml.Visibility.Visible : Microsoft.UI.Xaml.Visibility.Collapsed
                                });
                            }
                            OnPropertyChanged(nameof(AvailableAudioFiles));
                            System.Diagnostics.Debug.WriteLine($"NAVIGATION: Updated UI with {results.Length} refreshed items");
                        });
                        
                        // Save refreshed data to cache
                        var stemCounts = results.ToDictionary(r => r.AudioFile.Id, r => r.StemCount);
                        await _libraryCacheService.SaveCacheAsync(audioFiles, stemCounts);
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"NAVIGATION: Background refresh failed: {ex.Message}");
                }
            });
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"NAVIGATION: Error loading audio files: {ex.Message}");
            StatusMessage = $"Error loading files: {ex.Message}";
        }
    }

    [RelayCommand]
    public async Task AddAudioToMix(AudioFileDto audioFile)
    {
        await AddAudioToMixAsync(audioFile);
    }

    public async Task AddAudioToMixAsync(AudioFileDto audioFile)
    {
        System.Diagnostics.Debug.WriteLine("========================================");
        System.Diagnostics.Debug.WriteLine($"=== AddAudioToMixAsync START: {audioFile.OriginalFileName} ===");
        System.Diagnostics.Debug.WriteLine($"Timestamp: {DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}");
        System.Diagnostics.Debug.WriteLine($"Thread ID: {System.Threading.Thread.CurrentThread.ManagedThreadId}");
        System.Diagnostics.Debug.WriteLine($"AudioFile Details:");
        System.Diagnostics.Debug.WriteLine($"  - ID: {audioFile.Id}");
        System.Diagnostics.Debug.WriteLine($"  - OriginalFileName: {audioFile.OriginalFileName}");
        System.Diagnostics.Debug.WriteLine($"  - BlobUri: {audioFile.BlobUri}");
        System.Diagnostics.Debug.WriteLine($"Current state:");
        System.Diagnostics.Debug.WriteLine($"  - Track count: {Tracks.Count}");
        System.Diagnostics.Debug.WriteLine($"  - HasTracks: {HasTracks}");
        
        try
        {
            StatusMessage = $"Loading stems for {audioFile.OriginalFileName}...";
            System.Diagnostics.Debug.WriteLine($"Status message set: {StatusMessage}");
            
            // Check if stems exist for this audio file
            IEnumerable<StemDto>? stems = null;
            try
            {
                System.Diagnostics.Debug.WriteLine($"Calling API: GetStemsByAudioFileAsync({audioFile.Id})");
                stems = await _apiClient.GetStemsByAudioFileAsync(audioFile.Id);
                System.Diagnostics.Debug.WriteLine($"✓ API call successful - returned {stems?.Count() ?? 0} stems");
                
                if (stems != null && stems.Any())
                {
                    System.Diagnostics.Debug.WriteLine($"Stems found:");
                    foreach (var stem in stems)
                    {
                        System.Diagnostics.Debug.WriteLine($"  - {stem.Type} (ID: {stem.Id}, BlobUri: {stem.BlobUri})");
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"✗ EXCEPTION calling GetStemsByAudioFileAsync");
                System.Diagnostics.Debug.WriteLine($"  - Exception type: {ex.GetType().FullName}");
                System.Diagnostics.Debug.WriteLine($"  - Message: {ex.Message}");
                System.Diagnostics.Debug.WriteLine($"  - Stack trace:");
                System.Diagnostics.Debug.WriteLine(ex.StackTrace);
                StatusMessage = $"Error loading stems: {ex.Message}";
                throw;
            }
            
            if (stems != null && stems.Any())
            {
                System.Diagnostics.Debug.WriteLine($"✓ Found {stems.Count()} stems for {audioFile.OriginalFileName}");
                System.Diagnostics.Debug.WriteLine($"Processing stems and adding tracks...");
                
                // Add a track for each stem with instant preview waveforms
                int stemIndex = 0;
                foreach (var stem in stems)
                {
                    stemIndex++;
                    System.Diagnostics.Debug.WriteLine($"--- Processing stem {stemIndex}/{stems.Count()}: {stem.Type} ---");
                    StatusMessage = $"Adding track: {stem.Type}...";
                    
                    var trackId = Guid.NewGuid().ToString();
                    var cacheKey = $"stem_{stem.Id}";
                    System.Diagnostics.Debug.WriteLine($"  - Generated track ID: {trackId}");
                    System.Diagnostics.Debug.WriteLine($"  - Cache key: {cacheKey}");
                    
                    // Create track initially without waveform (declare outside try for lambda access)
                    MixTrack track;
                    
                    try
                    {
                        track = new MixTrack(_audioService)
                        {
                            Id = trackId,
                            Name = $"{audioFile.OriginalFileName} - {stem.Type}",
                            StemType = stem.Type.ToLower(),
                            Volume = 1.0,
                            IsMuted = false,
                            WaveformPath = "M 0,40 L 800,40" // Will be replaced by real waveform
                        };
                        
                        System.Diagnostics.Debug.WriteLine($"  - Track object created: {track.Name}");
                        
                        System.Diagnostics.Debug.WriteLine($"  - Track object created: {track.Name}");
                        System.Diagnostics.Debug.WriteLine($"  - Adding to Tracks collection (current count: {Tracks.Count})...");
                        
                        Tracks.Add(track);
                        
                        System.Diagnostics.Debug.WriteLine($"  ✓ Added stem track: {track.Name}. Total tracks: {Tracks.Count}");
                        System.Diagnostics.Debug.WriteLine($"  - Calling OnPropertyChanged(nameof(HasTracks))");
                        OnPropertyChanged(nameof(HasTracks));
                        System.Diagnostics.Debug.WriteLine($"  - HasTracks is now: {HasTracks}");
                        
                        // GENERATE REAL WAVEFORM IMMEDIATELY using NAudio
                        System.Diagnostics.Debug.WriteLine($"=== GENERATING REAL WAVEFORM FOR {stem.Type} ===");
                        var existingCached = await _cacheService.GetCachedAudioAsync(cacheKey);
                        if (existingCached != null)
                        {
                            System.Diagnostics.Debug.WriteLine($"Cached file found: {existingCached.Path}");
                            var realWaveform = await _fastWaveformService.GenerateWaveformFromAudioAsync(existingCached, 800, 80);
                            System.Diagnostics.Debug.WriteLine($"NAudio generated waveform! Length: {realWaveform.Length}");
                            System.Diagnostics.Debug.WriteLine($"First 100 chars: {(realWaveform.Length > 100 ? realWaveform.Substring(0, 100) : realWaveform)}");
                            track.WaveformPath = realWaveform;
                            System.Diagnostics.Debug.WriteLine($"Real waveform assigned to track");
                        }
                        else
                        {
                            System.Diagnostics.Debug.WriteLine($"No cached file found for {cacheKey}");
                        }
                    }
                    catch (Exception trackEx)
                    {
                        System.Diagnostics.Debug.WriteLine($"  ✗ EXCEPTION adding track for stem {stem.Type}");
                        System.Diagnostics.Debug.WriteLine($"    - Exception type: {trackEx.GetType().FullName}");
                        System.Diagnostics.Debug.WriteLine($"    - Message: {trackEx.Message}");
                        System.Diagnostics.Debug.WriteLine($"    - Stack trace:");
                        System.Diagnostics.Debug.WriteLine(trackEx.StackTrace);
                        throw;
                    }
                    
                    // Load audio into playback service in background
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            await _audioService.LoadTrackFromCacheAsync(
                                trackId,
                                cacheKey,
                                async () => await _apiClient.DownloadStemAsync(stem.Id) ?? Stream.Null,
                                $"{stem.Type}.wav"
                            );
                            System.Diagnostics.Debug.WriteLine($"Audio loaded into playback service for {stem.Type}");
                        }
                        catch (Exception ex)
                        {
                            System.Diagnostics.Debug.WriteLine($"Error loading audio for {stem.Type}: {ex.Message}");
                            StatusMessage = $"Error loading {stem.Type}";
                        }
                    });
                }
                
                OnPropertyChanged(nameof(HasTracks));
            }
            else
            {
                System.Diagnostics.Debug.WriteLine($"No stems found, adding original audio as single track");
                
                var trackId = Guid.NewGuid().ToString();
                
                var track = new MixTrack(_audioService)
                {
                    Id = trackId,
                    Name = audioFile.OriginalFileName,
                    Volume = 1.0,
                    IsMuted = false,
                    WaveformPath = "M 0,40 L 800,40" // Flat line placeholder
                };
                
                Tracks.Add(track);
                OnPropertyChanged(nameof(HasTracks));
                System.Diagnostics.Debug.WriteLine($"Added original track: {track.Name}. Total tracks: {Tracks.Count}");
            }
            
            System.Diagnostics.Debug.WriteLine($"=== AddAudioToMixAsync END ===");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"ERROR in AddAudioToMixAsync: {ex.Message}");
            StatusMessage = $"Error: {ex.Message}";
        }
    }

    [RelayCommand]
    private void Play()
    {
        System.Diagnostics.Debug.WriteLine("=== PLAY COMMAND TRIGGERED ===");
        System.Diagnostics.Debug.WriteLine($"HasTracks: {HasTracks}, Tracks.Count: {Tracks.Count}");
        System.Diagnostics.Debug.WriteLine($"IsPlaying: {IsPlaying}");
        
        if (IsPlaying)
        {
            System.Diagnostics.Debug.WriteLine("Pausing playback");
            _audioService.Pause();
        }
        else
        {
            System.Diagnostics.Debug.WriteLine("Starting playback");
            _audioService.Play();
        }
    }

    [RelayCommand]
    private void Pause()
    {
        _audioService.Pause();
    }

    [RelayCommand]
    private void Stop()
    {
        _audioService.Stop();
        IsPlaying = false;
        PlaybackCursorPosition = 0;
    }

    [RelayCommand]
    private void RemoveTrack(MixTrack track)
    {
        _audioService.RemoveTrack(track.Id);
        Tracks.Remove(track);
        OnPropertyChanged(nameof(HasTracks));
    }

    private string GenerateInstantSyntheticWaveform(string stemType, int width, int height)
    {
        // Generate instant synthetic waveform based on stem type
        var pathBuilder = new System.Text.StringBuilder();
        pathBuilder.Append($"M 0,{height / 2}");
        
        var random = new Random(stemType.GetHashCode()); // Consistent pattern per stem type
        
        if (stemType.ToLower().Contains("bass"))
        {
            // Bass: Lower frequency, higher amplitude
            for (int i = 0; i <= width; i += 2)
            {
                var wave = Math.Sin(i * 0.01) * 0.8;
                var y = height / 2 + wave * height * 0.4;
                pathBuilder.Append($" L {i},{y:F1}");
            }
        }
        else if (stemType.ToLower().Contains("drums"))
        {
            // Drums: Spiky pattern with bursts
            for (int i = 0; i <= width; i++)
            {
                var spike = i % 50 < 5 ? random.NextDouble() * 0.9 : random.NextDouble() * 0.3;
                var y = height / 2 + (random.NextDouble() - 0.5) * spike * height * 0.8;
                pathBuilder.Append($" L {i},{y:F1}");
            }
        }
        else if (stemType.ToLower().Contains("vocal"))
        {
            // Vocals: Higher frequency variation
            for (int i = 0; i <= width; i++)
            {
                var wave = Math.Sin(i * 0.03) * 0.7;
                var noise = (random.NextDouble() - 0.5) * 0.3;
                var y = height / 2 + (wave + noise) * height * 0.4;
                pathBuilder.Append($" L {i},{y:F1}");
            }
        }
        else
        {
            // Other: Smooth waveform
            for (int i = 0; i <= width; i++)
            {
                var wave = Math.Sin(i * 0.02) * 0.6;
                var noise = (random.NextDouble() - 0.5) * 0.2;
                var y = height / 2 + (wave + noise) * height * 0.4;
                pathBuilder.Append($" L {i},{y:F1}");
            }
        }
        
        return pathBuilder.ToString();
    }
}

public class AudioFileItemViewModel
{
    public AudioFileDto AudioFile { get; set; } = null!;
    public int StemCount { get; set; }
    public Microsoft.UI.Xaml.Visibility HasStems { get; set; }
}