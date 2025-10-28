using Windows.Media.Core;
using Windows.Media.Playback;
using Windows.Storage;
using Windows.Storage.Streams;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// Audio playback service using native Windows MediaPlayer API
/// This actually works unlike MAUI's MediaElement!
/// </summary>
public class AudioPlaybackService : IDisposable
{
    private readonly Dictionary<string, MediaPlayer> _players = new();
    private readonly Dictionary<string, double> _volumes = new();
    private readonly Dictionary<string, bool> _muteStates = new();
    private readonly AudioCacheService _cacheService;
    
    public event EventHandler<PlaybackStateChangedEventArgs>? PlaybackStateChanged;
    public event EventHandler<TimeSpan>? PositionChanged;
    
    private System.Threading.Timer? _positionTimer;
    private MediaPlayer? _masterPlayer;

    public bool IsPlaying => _masterPlayer?.PlaybackSession.PlaybackState == MediaPlaybackState.Playing;
    public TimeSpan Position => _masterPlayer?.PlaybackSession.Position ?? TimeSpan.Zero;
    public TimeSpan Duration => _masterPlayer?.PlaybackSession.NaturalDuration ?? TimeSpan.Zero;

    public AudioPlaybackService(AudioCacheService cacheService)
    {
        _cacheService = cacheService;
        
        // Position update timer
        _positionTimer = new System.Threading.Timer(_ =>
        {
            if (IsPlaying)
            {
                PositionChanged?.Invoke(this, Position);
            }
        }, null, TimeSpan.Zero, TimeSpan.FromMilliseconds(100));
    }

    public async Task LoadTrackAsync(string trackId, Stream audioStream, string fileName)
    {
        // Cache the audio file (uses existing cache if available)
        var cacheKey = $"{trackId}_{fileName}";
        var cachedFile = await _cacheService.CacheAudioAsync(cacheKey, audioStream, fileName);

        // Create MediaPlayer
        var player = new MediaPlayer
        {
            Source = MediaSource.CreateFromStorageFile(cachedFile),
            Volume = _volumes.GetValueOrDefault(trackId, 1.0),
            IsMuted = _muteStates.GetValueOrDefault(trackId, false)
        };

        // Store player
        if (_players.ContainsKey(trackId))
        {
            _players[trackId].Dispose();
        }
        _players[trackId] = player;

        // Set as master if first track
        if (_masterPlayer == null)
        {
            _masterPlayer = player;
            player.PlaybackSession.PlaybackStateChanged += (session, args) =>
            {
                PlaybackStateChanged?.Invoke(this, new PlaybackStateChangedEventArgs(session.PlaybackState));
            };
        }
    }

    public async Task LoadTrackFromCacheAsync(string trackId, string cacheKey, Func<Task<Stream>> audioStreamFactory, string fileName)
    {
        // Get or cache the audio file
        var cachedFile = await _cacheService.GetOrCacheAudioAsync(cacheKey, audioStreamFactory, fileName);

        // Create MediaPlayer
        var player = new MediaPlayer
        {
            Source = MediaSource.CreateFromStorageFile(cachedFile),
            Volume = _volumes.GetValueOrDefault(trackId, 1.0),
            IsMuted = _muteStates.GetValueOrDefault(trackId, false)
        };

        // Store player
        if (_players.ContainsKey(trackId))
        {
            _players[trackId].Dispose();
        }
        _players[trackId] = player;

        // Set as master if first track
        if (_masterPlayer == null)
        {
            _masterPlayer = player;
            player.PlaybackSession.PlaybackStateChanged += (session, args) =>
            {
                PlaybackStateChanged?.Invoke(this, new PlaybackStateChangedEventArgs(session.PlaybackState));
            };
        }
    }

    public void Play()
    {
        foreach (var player in _players.Values)
        {
            player.Play();
        }
    }

    public void Pause()
    {
        foreach (var player in _players.Values)
        {
            player.Pause();
        }
    }

    public void Stop()
    {
        foreach (var player in _players.Values)
        {
            player.Pause();
            player.PlaybackSession.Position = TimeSpan.Zero;
        }
    }

    public void Seek(TimeSpan position)
    {
        foreach (var player in _players.Values)
        {
            player.PlaybackSession.Position = position;
        }
    }

    public void SetTrackVolume(string trackId, double volume)
    {
        _volumes[trackId] = Math.Clamp(volume, 0.0, 1.0);
        if (_players.TryGetValue(trackId, out var player))
        {
            player.Volume = _volumes[trackId];
        }
    }

    public void SetTrackMute(string trackId, bool muted)
    {
        _muteStates[trackId] = muted;
        if (_players.TryGetValue(trackId, out var player))
        {
            player.IsMuted = muted;
        }
    }

    public void RemoveTrack(string trackId)
    {
        if (_players.TryGetValue(trackId, out var player))
        {
            if (player == _masterPlayer)
            {
                _masterPlayer = _players.Values.FirstOrDefault(p => p != player);
            }
            player.Dispose();
            _players.Remove(trackId);
        }
        _volumes.Remove(trackId);
        _muteStates.Remove(trackId);
    }

    public void Dispose()
    {
        _positionTimer?.Dispose();
        foreach (var player in _players.Values)
        {
            player.Dispose();
        }
        _players.Clear();
    }
}

public class PlaybackStateChangedEventArgs : EventArgs
{
    public MediaPlaybackState State { get; }
    
    public PlaybackStateChangedEventArgs(MediaPlaybackState state)
    {
        State = state;
    }
}
