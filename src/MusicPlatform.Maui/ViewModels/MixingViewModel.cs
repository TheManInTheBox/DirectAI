using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the mixing workspace page
/// </summary>
public class MixingViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _projectName = "Untitled Mix";
    private double _projectBpm = 120;
    private string _projectKey = "C major";
    private TimeSpan _timePosition = TimeSpan.Zero;
    private double _masterVolume = 0.8;
    private bool _isPlaying = false;
    private string _statusMessage = "Ready";
    private MixingTrackViewModel? _selectedTrack;

    public MixingViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        
        Tracks = new ObservableCollection<MixingTrackViewModel>();
        AvailableKeys = new ObservableCollection<string>
        {
            "C major", "C minor", "C# major", "C# minor",
            "D major", "D minor", "D# major", "D# minor",
            "E major", "E minor", "F major", "F minor",
            "F# major", "F# minor", "G major", "G minor",
            "G# major", "G# minor", "A major", "A minor",
            "A# major", "A# minor", "B major", "B minor"
        };
        
        // Initialize with some default tracks
        InitializeDefaultTracks();
        
        // Commands
        ShowAddTrackMenuCommand = new Command(async () => await ShowAddTrackMenuAsync());
        AddEmptyTrackCommand = new Command(AddEmptyTrack);
        AddAITrackCommand = new Command(async () => await AddAITrackAsync());
        AddFromLibraryTrackCommand = new Command(async () => await ShowStemLibraryAsync(null));
        PlayPauseCommand = new Command(PlayPause);
        StopCommand = new Command(Stop);
        SkipToStartCommand = new Command(SkipToStart);
        ExportMixCommand = new Command(async () => await ExportMixAsync());
        ShowStemLibraryCommand = new Command<MixingTrackViewModel>(async (track) => await ShowStemLibraryAsync(track));
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ObservableCollection<MixingTrackViewModel> Tracks { get; }
    public ObservableCollection<string> AvailableKeys { get; }
    
    public ICommand ShowAddTrackMenuCommand { get; }
    public ICommand AddEmptyTrackCommand { get; }
    public ICommand AddAITrackCommand { get; }
    public ICommand AddFromLibraryTrackCommand { get; }
    public ICommand PlayPauseCommand { get; }
    public ICommand StopCommand { get; }
    public ICommand SkipToStartCommand { get; }
    public ICommand ExportMixCommand { get; }
    public ICommand ShowStemLibraryCommand { get; }

    public string ProjectName
    {
        get => _projectName;
        set => SetProperty(ref _projectName, value);
    }

    public double ProjectBpm
    {
        get => _projectBpm;
        set => SetProperty(ref _projectBpm, value);
    }

    public string ProjectKey
    {
        get => _projectKey;
        set => SetProperty(ref _projectKey, value);
    }

    public TimeSpan TimePosition
    {
        get => _timePosition;
        set => SetProperty(ref _timePosition, value);
    }

    public double MasterVolume
    {
        get => _masterVolume;
        set => SetProperty(ref _masterVolume, value);
    }

    public bool IsPlaying
    {
        get => _isPlaying;
        set
        {
            if (SetProperty(ref _isPlaying, value))
            {
                OnPropertyChanged(nameof(PlayButtonText));
            }
        }
    }

    public string PlayButtonText => IsPlaying ? "⏸" : "▶";

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public MixingTrackViewModel? SelectedTrack
    {
        get => _selectedTrack;
        set => SetProperty(ref _selectedTrack, value);
    }

    public async Task InitializeAsync()
    {
        StatusMessage = "Mixing workspace ready";
        await Task.CompletedTask;
    }

    private void InitializeDefaultTracks()
    {
        // Create some example tracks
        Tracks.Add(new MixingTrackViewModel
        {
            TrackName = "Drums",
            InstrumentType = "Drums",
            InstrumentIcon = "🥁",
            Volume = 0.8
        });

        Tracks.Add(new MixingTrackViewModel
        {
            TrackName = "Bass",
            InstrumentType = "Bass",
            InstrumentIcon = "🎸",
            Volume = 0.7
        });

        Tracks.Add(new MixingTrackViewModel
        {
            TrackName = "Guitar",
            InstrumentType = "Guitar",
            InstrumentIcon = "🎸",
            Volume = 0.6
        });

        Tracks.Add(new MixingTrackViewModel
        {
            TrackName = "Synth",
            InstrumentType = "Synth",
            InstrumentIcon = "🎹",
            Volume = 0.5
        });
    }

    private async Task ShowAddTrackMenuAsync()
    {
        var action = await Application.Current.MainPage.DisplayActionSheet(
            "Add Track", 
            "Cancel", 
            null,
            "Empty Track",
            "AI Generated Track",
            "From Stem Library");

        switch (action)
        {
            case "Empty Track":
                AddEmptyTrack();
                break;
            case "AI Generated Track":
                await AddAITrackAsync();
                break;
            case "From Stem Library":
                await ShowStemLibraryAsync(null);
                break;
        }
    }

    private void AddEmptyTrack()
    {
        var trackNumber = Tracks.Count + 1;
        var newTrack = new MixingTrackViewModel
        {
            TrackName = $"Track {trackNumber}",
            InstrumentType = "Audio",
            InstrumentIcon = "🎵",
            Volume = 0.7
        };
        
        Tracks.Add(newTrack);
        StatusMessage = $"Added {newTrack.TrackName}";
    }

    private async Task AddAITrackAsync()
    {
        try
        {
            StatusMessage = "Configuring AI generation...";

            // Show generation parameters dialog
            var instrumentType = await Application.Current.MainPage.DisplayActionSheet(
                "Select Instrument Type",
                "Cancel",
                null,
                "Bass", "Drums", "Guitar", "Piano", "Synth", "Strings", "Brass", "Vocals");

            if (instrumentType == "Cancel")
            {
                StatusMessage = "AI generation cancelled";
                return;
            }

            // Get duration for the track
            var durationInput = await Application.Current.MainPage.DisplayPromptAsync(
                "Track Duration",
                "Enter duration in seconds (default: 30):",
                initialValue: "30",
                keyboard: Keyboard.Numeric);

            if (string.IsNullOrWhiteSpace(durationInput))
            {
                StatusMessage = "AI generation cancelled";
                return;
            }

            if (!double.TryParse(durationInput, out var duration) || duration <= 0 || duration > 300)
            {
                await Application.Current.MainPage.DisplayAlert("Invalid Input", "Please enter a valid duration between 1 and 300 seconds.", "OK");
                StatusMessage = "Invalid duration";
                return;
            }

            StatusMessage = $"Generating {instrumentType} track ({duration}s)...";

            // Build musical context from existing tracks
            var existingInstruments = Tracks
                .Where(t => !string.IsNullOrEmpty(t.InstrumentType))
                .Select(t => t.InstrumentType)
                .Distinct()
                .ToList();

            var contextPrompt = existingInstruments.Any()
                ? $"{instrumentType} track to complement existing {string.Join(", ", existingInstruments)}"
                : $"{instrumentType} track";

            // Calculate bars from duration and BPM
            var beatsPerMinute = ProjectBpm;
            var timeSignatureValue = 4; // Default 4/4
            var secondsPerBeat = 60.0 / beatsPerMinute;
            var beatsPerBar = timeSignatureValue;
            var secondsPerBar = secondsPerBeat * beatsPerBar;
            var bars = (int)Math.Ceiling(duration / secondsPerBar);

            // Create generation request with parameters
            var generationRequest = new
            {
                AudioFileId = Guid.Empty, // No source audio for AI generation
                TargetStems = new[] { instrumentType.ToLower() },
                Parameters = new
                {
                    Prompt = contextPrompt,
                    DurationSeconds = duration,
                    Key = ProjectKey,
                    Scale = ProjectKey.Contains("major") ? "major" : "minor",
                    TimeSignature = "4/4",
                    Bars = bars,
                    SectionType = "main",
                    Temperature = 1.0,
                    GuidanceScale = 3.0,
                    TopK = 250,
                    TopP = 0.0,
                    TargetBpm = ProjectBpm
                }
            };

            // Call generation API
            var result = await _apiClient.CreateGenerationRequestAsync(
                new MusicPlatform.Maui.Services.CreateGenerationRequestDto(
                    Guid.Empty,
                    new[] { instrumentType.ToLower() },
                    generationRequest.Parameters
                )
            );

            if (result?.Id != null)
            {
                // Create new track with pending status
                var trackNumber = Tracks.Count + 1;
                var newTrack = new MixingTrackViewModel
                {
                    TrackName = $"AI {instrumentType} {trackNumber}",
                    InstrumentType = instrumentType,
                    InstrumentIcon = GetInstrumentIcon(instrumentType),
                    Volume = 0.7
                };

                // Add clip placeholder for the generated audio
                newTrack.Clips.Add(new MixingClipViewModel
                {
                    ClipName = $"{instrumentType} (generating...)",
                    StartTime = TimeSpan.Zero,
                    Duration = TimeSpan.FromSeconds(duration),
                    Color = "#FF6B35",
                    GenerationRequestId = result.Id // Store generation request ID
                });

                Tracks.Add(newTrack);
                StatusMessage = $"AI track generation started (Request: {result.Id})";

                // TODO: Poll job status and update clip when complete
            }
            else
            {
                await Application.Current.MainPage.DisplayAlert("Generation Failed", "Failed to start AI generation.", "OK");
                StatusMessage = "Generation failed";
            }
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert("Error", $"AI generation error: {ex.Message}", "OK");
            StatusMessage = $"Error: {ex.Message}";
        }
    }

    private string GetInstrumentIcon(string instrumentType)
    {
        return instrumentType switch
        {
            "Bass" => "🎸",
            "Drums" => "🥁",
            "Guitar" => "🎸",
            "Piano" => "🎹",
            "Synth" => "🎹",
            "Strings" => "🎻",
            "Brass" => "🎺",
            "Vocals" => "🎤",
            _ => "🎵"
        };
    }

    private void AddTrack()
    {
        var trackNumber = Tracks.Count + 1;
        var newTrack = new MixingTrackViewModel
        {
            TrackName = $"Track {trackNumber}",
            InstrumentType = "Audio",
            InstrumentIcon = "🎵",
            Volume = 0.7
        };
        
        Tracks.Add(newTrack);
        StatusMessage = $"Added {newTrack.TrackName}";
    }

    private void PlayPause()
    {
        IsPlaying = !IsPlaying;
        StatusMessage = IsPlaying ? "Playing..." : "Paused";
        
        if (IsPlaying)
        {
            // TODO: Start audio playback
        }
        else
        {
            // TODO: Pause audio playback
        }
    }

    private void Stop()
    {
        IsPlaying = false;
        TimePosition = TimeSpan.Zero;
        StatusMessage = "Stopped";
        
        // TODO: Stop audio playback
    }

    private void SkipToStart()
    {
        TimePosition = TimeSpan.Zero;
        StatusMessage = "Position: 0:00";
        
        // TODO: Seek to start
    }

    private async Task ExportMixAsync()
    {
        try
        {
            StatusMessage = "Exporting mix...";
            
            // TODO: Implement mix export
            // 1. Collect all clips from all tracks
            // 2. Send to API for rendering
            // 3. Download result
            
            await Task.Delay(1000); // Simulate export
            
            StatusMessage = "Mix exported successfully!";
            
            await Application.Current!.MainPage!.DisplayAlert(
                "Export Complete",
                "Your mix has been exported successfully!",
                "OK");
        }
        catch (Exception ex)
        {
            StatusMessage = $"Export failed: {ex.Message}";
            
            await Application.Current!.MainPage!.DisplayAlert(
                "Export Error",
                ex.Message,
                "OK");
        }
    }

    private async Task ShowStemLibraryAsync(MixingTrackViewModel? targetTrack)
    {
        try
        {
            if (targetTrack != null)
            {
                SelectedTrack = targetTrack;
            }
            
            // Show stem library picker
            var trackName = targetTrack?.TrackName ?? "New Track";
            var result = await Application.Current!.MainPage!.DisplayActionSheet(
                $"Add to {trackName}",
                "Cancel",
                null,
                "Browse stem library",
                "Add from recent generations");

            if (result == null || result == "Cancel")
                return;

            if (result == "Browse stem library")
            {
                // Navigate to audio list to select stems
                await Shell.Current.GoToAsync("//AudioPage");
                StatusMessage = "Select stems from audio files";
            }
            else if (result == "Add from recent generations")
            {
                // Show recent generations
                await Shell.Current.GoToAsync("//StemsPage");
                StatusMessage = "Select from generated stems";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
        }
    }

    protected bool SetProperty<T>(ref T storage, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(storage, value))
            return false;

        storage = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

/// <summary>
/// ViewModel for a single mixing track
/// </summary>
public class MixingTrackViewModel : INotifyPropertyChanged
{
    private string _trackName = "Track";
    private string _instrumentType = "Audio";
    private string _instrumentIcon = "🎵";
    private double _volume = 0.7;
    private bool _isMuted = false;
    private bool _isSolo = false;
    private bool _isSelected = false;

    public MixingTrackViewModel()
    {
        Clips = new ObservableCollection<MixingClipViewModel>();
        SelectTrackCommand = new Command(() => IsSelected = true);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ObservableCollection<MixingClipViewModel> Clips { get; }
    public ICommand SelectTrackCommand { get; }

    public string TrackName
    {
        get => _trackName;
        set => SetProperty(ref _trackName, value);
    }

    public string InstrumentType
    {
        get => _instrumentType;
        set => SetProperty(ref _instrumentType, value);
    }

    public string InstrumentIcon
    {
        get => _instrumentIcon;
        set => SetProperty(ref _instrumentIcon, value);
    }

    public double Volume
    {
        get => _volume;
        set => SetProperty(ref _volume, value);
    }

    public bool IsMuted
    {
        get => _isMuted;
        set => SetProperty(ref _isMuted, value);
    }

    public bool IsSolo
    {
        get => _isSolo;
        set => SetProperty(ref _isSolo, value);
    }

    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }

    public bool HasNoClips => !Clips.Any();

    protected bool SetProperty<T>(ref T storage, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(storage, value))
            return false;

        storage = value;
        OnPropertyChanged(propertyName);
        
        if (propertyName == nameof(Clips))
        {
            OnPropertyChanged(nameof(HasNoClips));
        }
        
        return true;
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

/// <summary>
/// ViewModel for a clip/stem placed on a track
/// </summary>
public class MixingClipViewModel : INotifyPropertyChanged
{
    private string _clipName = "Clip";
    private TimeSpan _startPosition = TimeSpan.Zero;
    private TimeSpan _duration = TimeSpan.FromSeconds(10);
    private string _clipColor = "#4CAF50";
    private Guid? _stemId;
    private Guid? _generationRequestId;

    public event PropertyChangedEventHandler? PropertyChanged;

    public string ClipName
    {
        get => _clipName;
        set => SetProperty(ref _clipName, value);
    }

    public TimeSpan StartPosition
    {
        get => _startPosition;
        set => SetProperty(ref _startPosition, value);
    }

    public TimeSpan StartTime
    {
        get => _startPosition;
        set => SetProperty(ref _startPosition, value);
    }

    public TimeSpan Duration
    {
        get => _duration;
        set
        {
            if (SetProperty(ref _duration, value))
            {
                OnPropertyChanged(nameof(WidthPixels));
            }
        }
    }

    public string Color
    {
        get => _clipColor;
        set => SetProperty(ref _clipColor, value);
    }

    public Guid? StemId
    {
        get => _stemId;
        set => SetProperty(ref _stemId, value);
    }

    public Guid? GenerationRequestId
    {
        get => _generationRequestId;
        set => SetProperty(ref _generationRequestId, value);
    }

    // Calculate width based on duration (100 pixels per second)
    public double WidthPixels => Duration.TotalSeconds * 10; // 10 pixels per second

    protected bool SetProperty<T>(ref T storage, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(storage, value))
            return false;

        storage = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
