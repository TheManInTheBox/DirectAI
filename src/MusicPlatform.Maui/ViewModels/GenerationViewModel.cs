using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
using System.Text.Json;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the generation request page
/// </summary>
public class GenerationViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = string.Empty;
    private bool _isGenerating = false;
    private string? _audioFileId;
    private double _targetBpm = 120;
    private string _targetKey = "C major";
    private string _style = "rock";
    private string _prompt = string.Empty;
    private double _durationSeconds = 10;
    private double _maxQualityLength = 30;
    private GenerationRequestDto? _generationRequest;

    public GenerationViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        
        // Initialize reference stems (will be populated when initialized with audio file)
        ReferenceStems = new ObservableCollection<ReferenceStemOption>();
        
        // Initialize stem options
        AvailableStems = new ObservableCollection<StemOption>
        {
            new() { Name = "Guitar", IsSelected = true },
            new() { Name = "Bass", IsSelected = true },
            new() { Name = "Drums", IsSelected = true },
            new() { Name = "Vocals", IsSelected = false },
            new() { Name = "Piano", IsSelected = false },
            new() { Name = "Synth", IsSelected = false }
        };

        AvailableStyles = new ObservableCollection<string>
        {
            "rock", "jazz", "electronic", "classical", "hip-hop", "blues", "country", "funk"
        };
        
        AvailableKeys = new ObservableCollection<string>
        {
            "C major", "C minor", "C# major", "C# minor",
            "D major", "D minor", "D# major", "D# minor",
            "E major", "E minor", "F major", "F minor",
            "F# major", "F# minor", "G major", "G minor",
            "G# major", "G# minor", "A major", "A minor",
            "A# major", "A# minor", "B major", "B minor"
        };

        GenerateCommand = new Command(
            execute: async () =>
            {
                try
                {
                    await GenerateStemsAsync();
                }
                catch (Exception ex)
                {
                    StatusMessage = $"Command Error: {ex.Message}\n\nStack Trace: {ex.StackTrace}";
                    IsGenerating = false;
                }
            },
            canExecute: () => CanGenerate
        );
        ViewStemsCommand = new Command(async () => await NavigateToStemsAsync(), () => IsGenerationComplete);
        ClearReferenceStemsCommand = new Command(() => ClearReferenceStems());
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand GenerateCommand { get; }
    public ICommand ViewStemsCommand { get; }
    public ICommand ClearReferenceStemsCommand { get; }

    public ObservableCollection<ReferenceStemOption> ReferenceStems { get; }
    public ObservableCollection<StemOption> AvailableStems { get; }
    public ObservableCollection<string> AvailableStyles { get; }
    public ObservableCollection<string> AvailableKeys { get; }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public bool IsGenerating
    {
        get => _isGenerating;
        set
        {
            if (SetProperty(ref _isGenerating, value))
            {
                ((Command)GenerateCommand).ChangeCanExecute();
            }
        }
    }

    public double TargetBpm
    {
        get => _targetBpm;
        set => SetProperty(ref _targetBpm, value);
    }
    
    public string TargetKey
    {
        get => _targetKey;
        set => SetProperty(ref _targetKey, value);
    }
    
    public double MaxQualityLength
    {
        get => _maxQualityLength;
        set => SetProperty(ref _maxQualityLength, value);
    }

    public string Style
    {
        get => _style;
        set => SetProperty(ref _style, value);
    }

    public string Prompt
    {
        get => _prompt;
        set => SetProperty(ref _prompt, value);
    }

    public double DurationSeconds
    {
        get => _durationSeconds;
        set => SetProperty(ref _durationSeconds, value);
    }

    public GenerationRequestDto? GenerationRequest
    {
        get => _generationRequest;
        set
        {
            if (SetProperty(ref _generationRequest, value))
            {
                OnPropertyChanged(nameof(IsGenerationComplete));
                ((Command)ViewStemsCommand).ChangeCanExecute();
            }
        }
    }

    public bool CanGenerate => !IsGenerating && AvailableStems.Any(s => s.IsSelected);
    public bool IsGenerationComplete => GenerationRequest?.Status == "Completed";
    public bool HasReferenceStems => ReferenceStems.Any(s => s.IsSelected);

    public async Task InitializeAsync(string? audioFileId = null)
    {
        _audioFileId = audioFileId;
        
        // Load stems from global selection if available
        ReferenceStems.Clear();
        
        if (MainViewModel.GlobalSelectedStems.Any())
        {
            // Use globally selected stems from multiple sources
            foreach (var stemInfo in MainViewModel.GlobalSelectedStems)
            {
                ReferenceStems.Add(new ReferenceStemOption
                {
                    Id = stemInfo.StemId.ToString(),
                    Name = stemInfo.DisplayName, // Shows "AudioFile - StemType"
                    Info = stemInfo.StemType,
                    IsSelected = true // Pre-select all globally selected stems
                });
            }
            StatusMessage = $"{MainViewModel.GlobalSelectedStems.Count} stem(s) selected from multiple sources";
            OnPropertyChanged(nameof(HasReferenceStems));
        }
        else if (!string.IsNullOrEmpty(audioFileId) && Guid.TryParse(audioFileId, out var audioId))
        {
            // Fall back to loading stems from single audio file (legacy behavior)
            try
            {
                var stems = await _apiClient.GetStemsByAudioFileAsync(audioId);
                
                if (stems != null)
                {
                    foreach (var stem in stems)
                    {
                        ReferenceStems.Add(new ReferenceStemOption
                        {
                            Id = stem.Id.ToString(),
                            Name = stem.Type ?? "Unknown",
                            Info = $"{TimeSpan.FromSeconds(stem.DurationSeconds):mm\\:ss} • {stem.FileSizeBytes / 1024 / 1024:F1} MB",
                            IsSelected = false
                        });
                    }
                }
                
                StatusMessage = "Ready to generate stems";
                OnPropertyChanged(nameof(HasReferenceStems));
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error loading stems: {ex.Message}";
            }
        }
        else
        {
            StatusMessage = "No stems selected. Select stems from audio file details.";
            OnPropertyChanged(nameof(HasReferenceStems));
        }
    }

    private async Task GenerateStemsAsync()
    {
        try
        {
            IsGenerating = true;
            StatusMessage = "Preparing generation request with musical context...";

            var selectedStems = AvailableStems
                .Where(s => s.IsSelected)
                .Select(s => s.Name.ToLower())
                .ToArray();

            if (!selectedStems.Any())
            {
                StatusMessage = "Please select at least one stem type to generate";
                IsGenerating = false;
                return;
            }
            
            var selectedReferenceStems = ReferenceStems
                .Where(s => s.IsSelected)
                .Select(s => s.Id)
                .ToArray();
                
            if (!selectedReferenceStems.Any())
            {
                StatusMessage = "Please select at least one reference stem";
                IsGenerating = false;
                return;
            }

            StatusMessage = "Loading musical analysis from reference stems...";
            
            // Fetch full stem details to get notation, chords, beats, etc.
            var referenceStemDetails = new List<StemDto>();
            foreach (var stemId in selectedReferenceStems)
            {
                if (Guid.TryParse(stemId, out var guid))
                {
                    try
                    {
                        var stemDetail = await _apiClient.GetStemByIdAsync(guid);
                        if (stemDetail != null)
                        {
                            referenceStemDetails.Add(stemDetail);
                        }
                    }
                    catch (Exception ex)
                    {
                        StatusMessage = $"Warning: Could not load stem {stemId}: {ex.Message}";
                        await Task.Delay(1000); // Show warning briefly
                    }
                }
            }
            
            if (!referenceStemDetails.Any())
            {
                StatusMessage = "Error: Could not load any reference stem details. Please check API connection.";
                IsGenerating = false;
                return;
            }

            // Build musical context from reference stems
            var musicalContext = BuildMusicalContext(referenceStemDetails);
            
            StatusMessage = $"Creating generation request with {referenceStemDetails.Count} reference stem(s)...";

            // Serialize musical_context to JSON string to avoid complex object serialization issues
            var musicalContextJson = JsonSerializer.Serialize(musicalContext, new JsonSerializerOptions 
            { 
                WriteIndented = false 
            });

            var parameters = new Dictionary<string, object>
            {
                { "target_bpm", TargetBpm },
                { "target_key", TargetKey },
                { "max_quality_length", MaxQualityLength },
                { "duration_seconds", DurationSeconds },
                { "style", Style },
                { "reference_stem_ids", selectedReferenceStems },
                { "musical_context", musicalContextJson },  // Send as JSON string
                { "use_realistic_generation", true }
            };

            if (!string.IsNullOrWhiteSpace(Prompt))
            {
                parameters.Add("prompt", Prompt);
            }

            // Use first audio file ID from reference stems for the request
            var audioId = referenceStemDetails.First().AudioFileId;

            var request = new CreateGenerationRequestDto(
                audioId,
                selectedStems,
                parameters
            );

            var result = await _apiClient.CreateGenerationRequestAsync(request);

            if (result != null)
            {
                GenerationRequest = result;
                StatusMessage = $"✓ Generation request created with realistic musical context!\n" +
                              $"ID: {result.Id}\n" +
                              $"Status: {result.Status}\n" +
                              $"Reference Stems: {referenceStemDetails.Count}\n" +
                              $"Target: {TargetKey} @ {TargetBpm} BPM\n\n" +
                              $"Processing time: 2-5 minutes per stem.";
            }
            else
            {
                StatusMessage = "Failed to create generation request";
            }
        }
        catch (HttpRequestException httpEx)
        {
            StatusMessage = $"Network Error: {httpEx.Message}\n\nPlease check that the API is running.";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}\n\nStack Trace: {ex.StackTrace}";
        }
        finally
        {
            IsGenerating = false;
        }
    }

    private async Task NavigateToStemsAsync()
    {
        if (GenerationRequest == null) return;

        // Navigate to Stems tab
        await Shell.Current.GoToAsync("//StemsPage");
    }

    protected bool SetProperty<T>(ref T storage, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(storage, value))
            return false;

        storage = value;
        OnPropertyChanged(propertyName);
        return true;
    }
    
    private void ClearReferenceStems()
    {
        MainViewModel.GlobalSelectedStems.Clear();
        ReferenceStems.Clear();
        StatusMessage = "Reference stems cleared";
    }
    
    private Dictionary<string, object> BuildMusicalContext(List<StemDto> referenceStems)
    {
        var context = new Dictionary<string, object>();
        
        // Aggregate chord progressions from all reference stems
        var allChords = new List<object>();
        var allNotations = new List<object>();
        var allBeats = new List<object>();
        var allSections = new List<object>();
        
        foreach (var stem in referenceStems)
        {
            // Add source identification
            var stemContext = new Dictionary<string, object>
            {
                { "stem_id", stem.Id.ToString() },
                { "stem_type", stem.Type },
                { "source_key", stem.Key ?? "unknown" },
                { "source_bpm", stem.Bpm ?? 120.0 },
                { "time_signature", stem.TimeSignature ?? "4/4" }
            };
            
            // Parse and include chord progression
            if (!string.IsNullOrWhiteSpace(stem.ChordProgression))
            {
                try
                {
                    var chords = System.Text.Json.JsonSerializer.Deserialize<List<object>>(stem.ChordProgression);
                    if (chords != null && chords.Any())
                    {
                        stemContext["chord_progression"] = chords;
                        allChords.AddRange(chords);
                    }
                }
                catch { /* Ignore parsing errors */ }
            }
            
            // Parse and include notation data
            if (!string.IsNullOrWhiteSpace(stem.NotationData))
            {
                try
                {
                    var notation = System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, object>>(stem.NotationData);
                    if (notation != null)
                    {
                        stemContext["notation"] = notation;
                        allNotations.Add(new { stem_type = stem.Type, notation });
                    }
                }
                catch { /* Ignore parsing errors */ }
            }
            
            // Parse and include beats
            if (!string.IsNullOrWhiteSpace(stem.Beats))
            {
                try
                {
                    var beats = System.Text.Json.JsonSerializer.Deserialize<List<object>>(stem.Beats);
                    if (beats != null && beats.Any())
                    {
                        stemContext["beats"] = beats;
                        allBeats.AddRange(beats);
                    }
                }
                catch { /* Ignore parsing errors */ }
            }
            
            // Parse and include sections
            if (!string.IsNullOrWhiteSpace(stem.Sections))
            {
                try
                {
                    var sections = System.Text.Json.JsonSerializer.Deserialize<List<object>>(stem.Sections);
                    if (sections != null && sections.Any())
                    {
                        stemContext["sections"] = sections;
                        allSections.AddRange(sections);
                    }
                }
                catch { /* Ignore parsing errors */ }
            }
            
            // Add spectral features for realistic timbre matching
            if (stem.SpectralCentroid.HasValue)
            {
                stemContext["spectral_centroid"] = stem.SpectralCentroid.Value;
            }
            if (stem.RmsLevel.HasValue)
            {
                stemContext["rms_level"] = stem.RmsLevel.Value;
            }
            if (stem.ZeroCrossingRate.HasValue)
            {
                stemContext["zero_crossing_rate"] = stem.ZeroCrossingRate.Value;
            }
            
            context[$"reference_{stem.Type}"] = stemContext;
        }
        
        // Add aggregated musical features
        context["total_reference_stems"] = referenceStems.Count;
        context["reference_stem_types"] = referenceStems.Select(s => s.Type).Distinct().ToArray();
        
        if (allChords.Any())
        {
            context["aggregated_chords"] = allChords;
            context["total_chord_changes"] = allChords.Count;
        }
        
        if (allNotations.Any())
        {
            context["aggregated_notations"] = allNotations;
        }
        
        if (allBeats.Any())
        {
            context["aggregated_beats"] = allBeats;
            context["total_beats"] = allBeats.Count;
        }
        
        if (allSections.Any())
        {
            context["aggregated_sections"] = allSections;
        }
        
        // Add generation hints
        context["generation_hints"] = new Dictionary<string, object>
        {
            { "preserve_harmonic_structure", true },
            { "match_rhythmic_patterns", true },
            { "blend_timbres", true },
            { "maintain_musical_coherence", true }
        };
        
        return context;
    }

    protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}

public class StemOption : INotifyPropertyChanged
{
    private bool _isSelected;

    public string Name { get; set; } = string.Empty;
    
    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected != value)
            {
                _isSelected = value;
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsSelected)));
            }
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}

public class ReferenceStemOption : INotifyPropertyChanged
{
    private bool _isSelected;

    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Info { get; set; } = string.Empty;
    
    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected != value)
            {
                _isSelected = value;
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsSelected)));
            }
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}
