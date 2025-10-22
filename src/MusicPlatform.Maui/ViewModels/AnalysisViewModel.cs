using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Text.Json;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the analysis results page
/// </summary>
public class AnalysisViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = "Loading analysis...";
    private bool _isLoading = true;
    private AnalysisResultDto? _analysisResult;
    private AudioFileDto? _audioFile;
    private string? _audioFileId;
    private AudioInsightsDto? _insights;

    public AnalysisViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        RefreshCommand = new Command(async () => await LoadAnalysisAsync());
        GenerateStemsCommand = new Command(async () => await NavigateToGenerationAsync(), () => IsAnalysisComplete);
        ViewStemsCommand = new Command(async () => await NavigateToAudioFileDetailAsync());
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand RefreshCommand { get; }
    public ICommand GenerateStemsCommand { get; }
    public ICommand ViewStemsCommand { get; }

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

    public AnalysisResultDto? AnalysisResult
    {
        get => _analysisResult;
        set
        {
            if (SetProperty(ref _analysisResult, value))
            {
                OnPropertyChanged(nameof(IsAnalysisComplete));
                OnPropertyChanged(nameof(IsAnalysisPending));
                OnPropertyChanged(nameof(Bpm));
                OnPropertyChanged(nameof(Key));
                OnPropertyChanged(nameof(TimeSignature));
                OnPropertyChanged(nameof(Tuning));
                OnPropertyChanged(nameof(HasSections));
                OnPropertyChanged(nameof(HasChords));
                OnPropertyChanged(nameof(FlamingoDescription));
                OnPropertyChanged(nameof(FlamingoGenre));
                OnPropertyChanged(nameof(FlamingoMood));
                OnPropertyChanged(nameof(FlamingoQuality));
                OnPropertyChanged(nameof(FlamingoInstruments));
                ((Command)GenerateStemsCommand).ChangeCanExecute();
            }
        }
    }

    public bool IsAnalysisComplete => AnalysisResult?.Status == "Completed";
    public bool IsAnalysisPending => AnalysisResult?.Status == "Pending" || AnalysisResult?.Status == "Processing";

    public string? Bpm
    {
        get
        {
            var bpm = AnalysisResult?.Bpm ?? AudioFile?.Bpm;
            return bpm.HasValue ? bpm.Value.ToString("F1") + " BPM" : null;
        }
    }
    public string? Key => AnalysisResult?.Key ?? AudioFile?.Key;
    public string? TimeSignature => AnalysisResult?.TimeSignature ?? AudioFile?.TimeSignature;
    public string? Tuning => AnalysisResult?.Tuning;
    
    // Flamingo/semantic insights
    public string FlamingoDescription => _insights?.Description ?? "";
    public string FlamingoGenre => _insights?.Genre ?? "";
    public string FlamingoMood => _insights?.Mood ?? "";
    public string FlamingoQuality => _insights?.Quality ?? "";
    public string FlamingoInstruments => _insights?.Instruments != null && _insights.Instruments.Any()
        ? string.Join(", ", _insights.Instruments)
        : string.Empty;
    
    // Audio file metadata for display
    public AudioFileDto? AudioFile
    {
        get => _audioFile;
        set
        {
            if (SetProperty(ref _audioFile, value))
            {
                OnPropertyChanged(nameof(AlbumArtworkUri));
                OnPropertyChanged(nameof(DisplayTitle));
                OnPropertyChanged(nameof(DisplayArtist));
                OnPropertyChanged(nameof(DisplayAlbum));
                OnPropertyChanged(nameof(HasAlbumArtwork));
                OnPropertyChanged(nameof(HasMetadata));
            }
        }
    }
    
    public string? AlbumArtworkUri => AudioFile?.AlbumArtworkUri;
    public string DisplayTitle => AudioFile?.Title ?? AudioFile?.OriginalFileName ?? "Unknown Track";
    public string DisplayArtist => AudioFile?.Artist ?? "Unknown Artist";
    public string DisplayAlbum => AudioFile?.Album ?? string.Empty;
    public bool HasAlbumArtwork => !string.IsNullOrWhiteSpace(AudioFile?.AlbumArtworkUri);
    public bool HasMetadata => !string.IsNullOrWhiteSpace(AudioFile?.Title) || 
                               !string.IsNullOrWhiteSpace(AudioFile?.Artist);

    public bool HasSections => Sections.Any();
    public bool HasChords => Chords.Any();

    public List<SectionInfo> Sections
    {
        get
        {
            if (string.IsNullOrEmpty(AnalysisResult?.JamsData))
                return new List<SectionInfo>();

            try
            {
                var jams = JsonSerializer.Deserialize<JamsDocument>(AnalysisResult.JamsData);
                var sectionsAnnotation = jams?.file_metadata?.annotations?
                    .FirstOrDefault(a => a.namespace_value == "segment_open");

                if (sectionsAnnotation?.data == null)
                    return new List<SectionInfo>();

                return sectionsAnnotation.data
                    .Select(d => new SectionInfo
                    {
                        Label = d.value?.label ?? "Unknown",
                        StartTime = d.time,
                        Duration = d.duration
                    })
                    .ToList();
            }
            catch
            {
                return new List<SectionInfo>();
            }
        }
    }

    public List<ChordInfo> Chords
    {
        get
        {
            if (string.IsNullOrEmpty(AnalysisResult?.JamsData))
                return new List<ChordInfo>();

            try
            {
                var jams = JsonSerializer.Deserialize<JamsDocument>(AnalysisResult.JamsData);
                var chordsAnnotation = jams?.file_metadata?.annotations?
                    .FirstOrDefault(a => a.namespace_value == "chord");

                if (chordsAnnotation?.data == null)
                    return new List<ChordInfo>();

                return chordsAnnotation.data
                    .Select(d => new ChordInfo
                    {
                        Chord = d.value?.label ?? "N",
                        StartTime = d.time,
                        Duration = d.duration
                    })
                    .ToList();
            }
            catch
            {
                return new List<ChordInfo>();
            }
        }
    }

    public async Task InitializeAsync(string audioFileId)
    {
        _audioFileId = audioFileId;
        await LoadAnalysisAsync();
    }

    private async Task LoadAnalysisAsync()
    {
        if (string.IsNullOrEmpty(_audioFileId)) return;

        try
        {
            IsLoading = true;
            StatusMessage = "Loading analysis results...";

            if (!Guid.TryParse(_audioFileId, out var id))
            {
                StatusMessage = "Invalid audio file ID";
                return;
            }

            // Load both audio file metadata and analysis result
            var audioFileTask = _apiClient.GetAudioFileAsync(id);
            var analysisTask = _apiClient.GetAnalysisAsync(id);
            var insightsTask = _apiClient.GetAudioInsightsAsync(id);
            await Task.WhenAll(audioFileTask, analysisTask, insightsTask);

            AudioFile = await audioFileTask;
            var result = await analysisTask;
            _insights = await insightsTask;

            if (result == null)
            {
                StatusMessage = "Analysis not found";
                return;
            }

            AnalysisResult = result;

            StatusMessage = result.Status switch
            {
                "Completed" => "Analysis complete",
                "Pending" => "Analysis pending... Refresh to check status",
                "Processing" => "Analysis in progress... Refresh to check status",
                "Failed" => "Analysis failed",
                _ => $"Status: {result.Status}"
            };
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error loading analysis: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
            // Notify insights-bound properties even if analysis fails to ensure UI updates gracefully
            OnPropertyChanged(nameof(FlamingoDescription));
            OnPropertyChanged(nameof(FlamingoGenre));
            OnPropertyChanged(nameof(FlamingoMood));
            OnPropertyChanged(nameof(FlamingoQuality));
            OnPropertyChanged(nameof(FlamingoInstruments));
        }
    }

    private async Task NavigateToGenerationAsync()
    {
        if (string.IsNullOrEmpty(_audioFileId)) return;

        // Navigate to Generation tab
        await Shell.Current.GoToAsync("//GenerationPage");
        
        // Find the Generation page and initialize it
        var generationPage = Shell.Current.CurrentPage as MusicPlatform.Maui.Pages.GenerationPage;
        if (generationPage != null)
        {
            await generationPage.InitializeWithAudioFileAsync(_audioFileId);
        }
    }

    private async Task NavigateToAudioFileDetailAsync()
    {
        if (string.IsNullOrEmpty(_audioFileId)) return;

        var navigationParameter = new Dictionary<string, object>
        {
            { "AudioFileId", _audioFileId }
        };

        await Shell.Current.GoToAsync("AudioFileDetailPage", navigationParameter);
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

#region Models

public class SectionInfo
{
    public string Label { get; set; } = string.Empty;
    public double StartTime { get; set; }
    public double Duration { get; set; }
    public string TimeRange => $"{StartTime:F1}s - {(StartTime + Duration):F1}s";
}

public class ChordInfo
{
    public string Chord { get; set; } = string.Empty;
    public double StartTime { get; set; }
    public double Duration { get; set; }
    public string TimeRange => $"{StartTime:F1}s";
}

// JAMS JSON structure
public class JamsDocument
{
    public FileMetadata? file_metadata { get; set; }
}

public class FileMetadata
{
    public List<Annotation>? annotations { get; set; }
}

public class Annotation
{
    public string? namespace_value { get; set; }
    public List<AnnotationData>? data { get; set; }
}

public class AnnotationData
{
    public double time { get; set; }
    public double duration { get; set; }
    public AnnotationValue? value { get; set; }
}

public class AnnotationValue
{
    public string? label { get; set; }
}

#endregion
