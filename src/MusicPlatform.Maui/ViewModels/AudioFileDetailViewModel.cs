using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the audio file detail page showing stems and analysis
/// </summary>
public class AudioFileDetailViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _audioFileId = string.Empty;
    private string _statusMessage = string.Empty;
    private bool _isLoading = false;
    private AudioFileDto? _audioFile;
    private AnalysisResultDto? _analysisResult;
    private ObservableCollection<StemDetailItemViewModel> _stems = new();

    private bool _showStemsLoading;
    private bool _showStemsList;
    private bool _showNoStemsMessage;
    
    // Stem selection properties
    private bool _isStemSelectionMode = false;

    public AudioFileDetailViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        ToggleStemSelectionModeCommand = new Command(() => ToggleStemSelectionMode());
        GenerateFromSelectedStemsCommand = new Command(async () => await GenerateFromSelectedStemsAsync(), () => HasSelectedStems);
    }
    
    public ICommand ToggleStemSelectionModeCommand { get; }
    public ICommand GenerateFromSelectedStemsCommand { get; }

    public event PropertyChangedEventHandler? PropertyChanged;

    public bool ShowStemsLoading
    {
        get => _showStemsLoading;
        set => SetProperty(ref _showStemsLoading, value);
    }

    public bool ShowStemsList
    {
        get => _showStemsList;
        set => SetProperty(ref _showStemsList, value);
    }

    public bool ShowNoStemsMessage
    {
        get => _showNoStemsMessage;
        set => SetProperty(ref _showNoStemsMessage, value);
    }
    
    public bool IsStemSelectionMode
    {
        get => _isStemSelectionMode;
        set
        {
            if (SetProperty(ref _isStemSelectionMode, value))
            {
                // Clear selection when exiting selection mode
                if (!value)
                {
                    foreach (var stem in Stems)
                    {
                        stem.IsSelected = false;
                    }
                }
                OnPropertyChanged(nameof(HasSelectedStems));
            }
        }
    }
    
    public bool HasSelectedStems => Stems.Any(s => s.IsSelected);
    
    public int SelectedStemsCount => Stems.Count(s => s.IsSelected);

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public bool IsLoading
    {
        get => _isLoading;
        set => SetProperty(ref _isLoading, value);
    }

    public AudioFileDto? AudioFile
    {
        get => _audioFile;
        set
        {
            if (SetProperty(ref _audioFile, value))
            {
                OnPropertyChanged(nameof(DisplayTitle));
                OnPropertyChanged(nameof(DisplayArtist));
                OnPropertyChanged(nameof(DisplayAlbum));
                OnPropertyChanged(nameof(AlbumArtworkUri));
                OnPropertyChanged(nameof(HasAlbumArtwork));
                OnPropertyChanged(nameof(Format));
                OnPropertyChanged(nameof(DurationFormatted));
                OnPropertyChanged(nameof(Bitrate));
                OnPropertyChanged(nameof(HasBitrate));
                OnPropertyChanged(nameof(SampleRate));
                OnPropertyChanged(nameof(Channels));
                // Analysis properties
                OnPropertyChanged(nameof(HasAnalysis));
                OnPropertyChanged(nameof(Bpm));
                OnPropertyChanged(nameof(Key));
                OnPropertyChanged(nameof(TimeSignature));
            }
        }
    }

    public AnalysisResultDto? AnalysisResult
    {
        get => _analysisResult;
        set
        {
            if (SetProperty(ref _analysisResult, value))
            {
                OnPropertyChanged(nameof(HasAnalysis));
                OnPropertyChanged(nameof(Bpm));
                OnPropertyChanged(nameof(Key));
                OnPropertyChanged(nameof(TimeSignature));
                OnPropertyChanged(nameof(Tuning));
                OnPropertyChanged(nameof(HasChordProgression));
                OnPropertyChanged(nameof(ChordProgressionSummary));
            }
        }
    }

    public ObservableCollection<StemDetailItemViewModel> Stems
    {
        get => _stems;
        set => SetProperty(ref _stems, value);
    }

    // Display properties
    public string DisplayTitle => AudioFile?.Title ?? AudioFile?.OriginalFileName ?? "Unknown Track";
    public string DisplayArtist => AudioFile?.Artist ?? "Unknown Artist";
    public string DisplayAlbum => AudioFile?.Album ?? string.Empty;
    public string? AlbumArtworkUri => AudioFile?.AlbumArtworkUri;
    public bool HasAlbumArtwork => !string.IsNullOrWhiteSpace(AudioFile?.AlbumArtworkUri);
    public string Format => AudioFile?.Format?.ToUpper() ?? "UNKNOWN";
    public string DurationFormatted => AudioFile?.Duration.ToString(@"mm\:ss") ?? "0:00";
    public int? Bitrate => AudioFile?.Bitrate;
    public bool HasBitrate => AudioFile?.Bitrate.HasValue ?? false;
    public string SampleRate => AudioFile?.SampleRate.HasValue == true ? $"{AudioFile.SampleRate.Value / 1000.0:F1} kHz" : "Unknown";
    public string Channels => AudioFile?.Channels switch
    {
        1 => "Mono",
        2 => "Stereo",
        int ch => $"{ch} channels",
        _ => "Unknown"
    };

    // Analysis properties - now from AudioFile directly
    public bool HasAnalysis => AudioFile?.Bpm != null && AudioFile?.Key != null;
    public string? Bpm => AudioFile?.Bpm?.ToString("F1");
    public string? Key => AudioFile?.Key;
    public string? TimeSignature => AudioFile?.TimeSignature;
    public string? Tuning => !string.IsNullOrEmpty(AnalysisResult?.Tuning) ? AnalysisResult.Tuning + " Hz" : null;

    // Chord Progression properties (from stems - displayed at global level)
    public bool HasChordProgression => Stems.Any(s => s.HasChordProgression);
    public string? ChordProgressionSummary
    {
        get
        {
            var stemWithChords = Stems.FirstOrDefault(s => s.HasChordProgression);
            return stemWithChords?.ChordProgressionSummary;
        }
    }

    public void SetAudioFileId(string audioFileId)
    {
        _audioFileId = audioFileId;
    }

    public async Task InitializeAsync()
    {
        if (string.IsNullOrEmpty(_audioFileId))
        {
            Console.WriteLine("❌ DEBUG: No audio file ID set");
            StatusMessage = "No audio file selected";
            UpdateStemVisibility(showList: false, showMessage: true);
            return;
        }

        try
        {
            IsLoading = true;
            UpdateStemVisibility(showLoading: true);
            StatusMessage = "Loading details...";

            if (!Guid.TryParse(_audioFileId, out var id))
            {
                StatusMessage = "Invalid audio file ID";
                UpdateStemVisibility(showList: false, showMessage: true);
                return;
            }

            // Load audio file metadata
            AudioFile = await _apiClient.GetAudioFileAsync(id);

            if (AudioFile == null)
            {
                StatusMessage = "Audio file not found";
                UpdateStemVisibility(showList: false, showMessage: true);
                return;
            }

            // Load analysis results
            try
            {
                AnalysisResult = await _apiClient.GetAnalysisAsync(id);
            }
            catch (Exception ex)
            {
                // Analysis may not exist yet, that's okay
            }

            // Load stems
            await LoadStemsAsync(id);

            StatusMessage = string.Empty;
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error loading details: {ex.Message}";
            UpdateStemVisibility(showList: false, showMessage: true);
        }
        finally
        {
            IsLoading = false;
            ShowStemsLoading = false;
            
            // Final check: if we have stems, show the list
            if (Stems.Count > 0)
            {
                UpdateStemVisibility(showList: true);
            }
        }
    }

    private async Task LoadStemsAsync(Guid audioFileId)
    {
        try
        {
            StatusMessage = "Loading stems...";
            var stems = await _apiClient.GetStemsByAudioFileAsync(audioFileId);
            
            Stems.Clear();
            if (stems != null && stems.Any())
            {
                foreach (var stem in stems.OrderBy(s => s.Type))
                {
                    var stemViewModel = new StemDetailItemViewModel(stem, _apiClient);
                    // Subscribe to property changes to update command state
                    stemViewModel.PropertyChanged += (s, e) =>
                    {
                        if (e.PropertyName == nameof(StemDetailItemViewModel.IsSelected))
                        {
                            OnPropertyChanged(nameof(HasSelectedStems));
                            OnPropertyChanged(nameof(SelectedStemsCount));
                            ((Command)GenerateFromSelectedStemsCommand).ChangeCanExecute();
                        }
                    };
                    Stems.Add(stemViewModel);
                }
                UpdateStemVisibility(showList: true);
                
                // Notify chord progression properties since they depend on stems
                OnPropertyChanged(nameof(HasChordProgression));
                OnPropertyChanged(nameof(ChordProgressionSummary));
            }
            else
            {
                StatusMessage = "No stems available for this audio file";
                UpdateStemVisibility(showMessage: true);
            }
            
            // Clear status message after 3 seconds if successful
            if (Stems.Any())
            {
                await Task.Delay(3000);
                StatusMessage = string.Empty;
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error loading stems: {ex.Message}";
            UpdateStemVisibility(showMessage: true);
        }
    }

    private void UpdateStemVisibility(bool showLoading = false, bool showList = false, bool showMessage = false)
    {
        ShowStemsLoading = showLoading;
        ShowStemsList = showList;
        ShowNoStemsMessage = showMessage;
    }
    
    private void ToggleStemSelectionMode()
    {
        IsStemSelectionMode = !IsStemSelectionMode;
    }
    
    private async Task GenerateFromSelectedStemsAsync()
    {
        var selectedStems = Stems.Where(s => s.IsSelected).ToList();
        if (selectedStems.Count == 0)
        {
            StatusMessage = "Please select at least one stem";
            return;
        }
        
        // Add selected stems to global collection (or update if coming from single source)
        foreach (var stem in selectedStems)
        {
            var stemInfo = new SelectedStemInfo
            {
                StemId = stem.Id,
                AudioFileName = AudioFile?.Title ?? "Unknown",
                StemType = stem.StemType
            };
            
            // Check if stem already exists in global collection
            if (!MainViewModel.GlobalSelectedStems.Any(s => s.StemId == stem.Id))
            {
                MainViewModel.GlobalSelectedStems.Add(stemInfo);
            }
        }
        
        var totalCount = MainViewModel.GlobalSelectedStems.Count;
        StatusMessage = $"✓ {selectedStems.Count} stem(s) added! Total: {totalCount} selected";
        
        // Show confirmation alert
        var goToGeneration = await Application.Current!.Windows[0].Page!.DisplayAlert(
            "Stems Added to Selection",
            $"You've selected {selectedStems.Count} stem(s) from '{AudioFile?.Title}'.\n\n" +
            $"Total stems selected: {totalCount}\n\n" +
            $"Would you like to:\n" +
            $"• Continue selecting from other audio files, or\n" +
            $"• Go to Generation page now?",
            "Go to Generation",
            "Keep Selecting"
        );
        
        if (goToGeneration)
        {
            // Navigate to generation page
            await Shell.Current.GoToAsync("generation");
        }
        else
        {
            // Clear selection mode and go back to browse more
            IsStemSelectionMode = false;
            await Shell.Current.GoToAsync("..");
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
/// ViewModel for individual stem in the detail view
/// </summary>
public class StemDetailItemViewModel : INotifyPropertyChanged
{
    private readonly StemDto _stem;
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = string.Empty;
    private bool _isSelected = false;

    public StemDetailItemViewModel(StemDto stem, MusicPlatformApiClient apiClient)
    {
        _stem = stem;
        _apiClient = apiClient;
        PlayCommand = new Command(async () => await PlayStemAsync());
        ViewNotationCommand = new Command(async () => await ViewNotationAsync());
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand PlayCommand { get; }
    public ICommand ViewNotationCommand { get; }

    public Guid Id => _stem.Id;
    public string StemType => _stem.Type.ToUpper();
    public string Duration => _stem.DurationSeconds.ToString("F1") + "s";
    public string FileSizeFormatted => FormatFileSize(_stem.FileSizeBytes);
    public string? Key => _stem.Key;
    public bool HasKey => !string.IsNullOrWhiteSpace(_stem.Key);
    public double? Bpm => _stem.Bpm;
    public bool HasBpm => _stem.Bpm.HasValue;
    
    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected != value)
            {
                _isSelected = value;
                OnPropertyChanged();
            }
        }
    }
    
    // Chord Progression properties
    public bool HasChordProgression => !string.IsNullOrWhiteSpace(_stem.ChordProgression);
    public string? ChordProgressionSummary
    {
        get
        {
            if (string.IsNullOrWhiteSpace(_stem.ChordProgression))
                return null;
                
            try
            {
                var chords = System.Text.Json.JsonSerializer.Deserialize<List<ChordDataModel>>(_stem.ChordProgression);
                if (chords == null || chords.Count == 0) return null;
                
                // Get unique chords in order
                var uniqueChords = new List<string>();
                foreach (var chord in chords)
                {
                    if (!uniqueChords.Contains(chord.Chord))
                        uniqueChords.Add(chord.Chord);
                }
                
                return $"{chords.Count} chord changes: {string.Join(" → ", uniqueChords.Take(8))}{(uniqueChords.Count > 8 ? "..." : "")}";
            }
            catch
            {
                return "Chord progression available";
            }
        }
    }
    
    // Notation properties
    public bool HasNotation => !string.IsNullOrWhiteSpace(_stem.NotationData);
    public string? NotationPreview
    {
        get
        {
            if (string.IsNullOrWhiteSpace(_stem.NotationData))
                return null;
                
            try
            {
                var notation = System.Text.Json.JsonSerializer.Deserialize<NotationDataModel>(_stem.NotationData);
                if (notation == null) return null;
                
                // Create a preview based on notation type
                if (notation.Type == "drum_pattern" && notation.DrumPattern?.Length > 0)
                {
                    var preview = notation.DrumPattern[0];
                    return $"Kick: {preview.Kick}\nSnare: {preview.Snare}\nHH: {preview.HiHat}";
                }
                else if (notation.Type == "tablature" && notation.Tablature?.Length > 0)
                {
                    var preview = notation.Tablature[0];
                    return $"{preview.String}: {preview.Fret} ({preview.Technique})";
                }
                else if (notation.Type == "chord_shapes" && notation.ChordShapes?.Length > 0)
                {
                    var preview = notation.ChordShapes[0];
                    return $"{preview.ChordName}: {string.Join("-", preview.Frets)}";
                }
                
                return "Notation available";
            }
            catch
            {
                return "Notation available";
            }
        }
    }

    public string StatusMessage
    {
        get => _statusMessage;
        set
        {
            _statusMessage = value;
            OnPropertyChanged();
        }
    }

    private async Task ViewNotationAsync()
    {
        try
        {
            if (string.IsNullOrWhiteSpace(_stem.NotationData))
            {
                StatusMessage = "No notation data available";
                return;
            }

            // Navigate to notation detail page or show popup
            // For now, show a simple alert with formatted notation
            var notation = System.Text.Json.JsonSerializer.Deserialize<NotationDataModel>(_stem.NotationData);
            if (notation == null)
            {
                StatusMessage = "Failed to parse notation data";
                return;
            }

            var notationText = FormatNotationForDisplay(notation);
            await Application.Current!.MainPage!.DisplayAlert(
                $"{StemType} Notation",
                notationText,
                "Close");
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error viewing notation: {ex.Message}";
        }
    }

    private string FormatNotationForDisplay(NotationDataModel notation)
    {
        var sb = new System.Text.StringBuilder();
        
        sb.AppendLine($"Type: {notation.Type}");
        sb.AppendLine($"Confidence: {notation.Confidence:P0}");
        sb.AppendLine();

        if (notation.Type == "drum_pattern" && notation.DrumPattern != null)
        {
            sb.AppendLine("Drum Pattern:");
            foreach (var pattern in notation.DrumPattern.Take(10))
            {
                sb.AppendLine($"  Beat {pattern.Beat}: Kick={pattern.Kick}, Snare={pattern.Snare}, HH={pattern.HiHat}");
            }
            if (notation.DrumPattern.Length > 10)
                sb.AppendLine($"  ... and {notation.DrumPattern.Length - 10} more beats");
        }
        else if (notation.Type == "tablature" && notation.Tablature != null)
        {
            sb.AppendLine("Tablature:");
            foreach (var note in notation.Tablature.Take(20))
            {
                sb.AppendLine($"  {note.Time:F2}s: String {note.String}, Fret {note.Fret} ({note.Technique})");
            }
            if (notation.Tablature.Length > 20)
                sb.AppendLine($"  ... and {notation.Tablature.Length - 20} more notes");
        }
        else if (notation.Type == "chord_shapes" && notation.ChordShapes != null)
        {
            sb.AppendLine("Chord Shapes:");
            foreach (var chord in notation.ChordShapes.Take(10))
            {
                sb.AppendLine($"  {chord.Time:F2}s: {chord.ChordName} - {string.Join("-", chord.Frets)}");
            }
            if (notation.ChordShapes.Length > 10)
                sb.AppendLine($"  ... and {notation.ChordShapes.Length - 10} more chords");
        }

        return sb.ToString();
    }

    private async Task PlayStemAsync()
    {
        try
        {
            StatusMessage = "Playing stem...";

            // Download the stem to a temp file and play it
            var stream = await _apiClient.DownloadStemAsync(_stem.Id);
            if (stream == null)
            {
                StatusMessage = "Failed to load stem";
                return;
            }

            // Save to temp file
            var tempPath = Path.Combine(Path.GetTempPath(), $"{_stem.Type}_{_stem.Id}.wav");
            using (var fileStream = File.Create(tempPath))
            {
                await stream.CopyToAsync(fileStream);
            }

            // Play using system default player
            await Launcher.OpenAsync(new OpenFileRequest
            {
                File = new ReadOnlyFile(tempPath)
            });

            StatusMessage = "Playing...";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
        }
    }

    private static string FormatFileSize(long bytes)
    {
        string[] sizes = { "B", "KB", "MB", "GB" };
        double len = bytes;
        int order = 0;
        while (len >= 1024 && order < sizes.Length - 1)
        {
            order++;
            len /= 1024;
        }
        return $"{len:0.##} {sizes[order]}";
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

// Models for chord progression and notation data deserialization
public class ChordDataModel
{
    [System.Text.Json.Serialization.JsonPropertyName("chord")]
    public string Chord { get; set; } = string.Empty;
    
    [System.Text.Json.Serialization.JsonPropertyName("start_time")]
    public double StartTime { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("end_time")]
    public double EndTime { get; set; }
    
    [System.Text.Json.Serialization.JsonPropertyName("confidence")]
    public double Confidence { get; set; }
}

public class NotationDataModel
{
    public string Type { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public DrumPatternItem[]? DrumPattern { get; set; }
    public TablatureItem[]? Tablature { get; set; }
    public ChordShapeItem[]? ChordShapes { get; set; }
}

public class DrumPatternItem
{
    public int Beat { get; set; }
    public int Kick { get; set; }
    public int Snare { get; set; }
    public int HiHat { get; set; }
    public int Crash { get; set; }
    public int Ride { get; set; }
    public int Tom { get; set; }
}

public class TablatureItem
{
    public double Time { get; set; }
    public int String { get; set; }
    public int Fret { get; set; }
    public string Technique { get; set; } = string.Empty;
    public double Duration { get; set; }
}

public class ChordShapeItem
{
    public double Time { get; set; }
    public string ChordName { get; set; } = string.Empty;
    public int[] Frets { get; set; } = Array.Empty<int>();
    public double Duration { get; set; }
}
