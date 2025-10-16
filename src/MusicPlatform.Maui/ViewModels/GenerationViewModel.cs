using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
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
    private string _style = "rock";
    private string _prompt = string.Empty;
    private double _durationSeconds = 10;
    private GenerationRequestDto? _generationRequest;

    public GenerationViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        
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

        GenerateCommand = new Command(async () => await GenerateStemsAsync(), () => CanGenerate);
        ViewStemsCommand = new Command(async () => await NavigateToStemsAsync(), () => IsGenerationComplete);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand GenerateCommand { get; }
    public ICommand ViewStemsCommand { get; }

    public ObservableCollection<StemOption> AvailableStems { get; }
    public ObservableCollection<string> AvailableStyles { get; }

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

    public async Task InitializeAsync(string audioFileId)
    {
        _audioFileId = audioFileId;
        StatusMessage = "Ready to generate stems";
    }

    private async Task GenerateStemsAsync()
    {
        if (string.IsNullOrEmpty(_audioFileId)) return;

        try
        {
            IsGenerating = true;
            StatusMessage = "Submitting generation request...";

            if (!Guid.TryParse(_audioFileId, out var audioId))
            {
                StatusMessage = "Invalid audio file ID";
                return;
            }

            var selectedStems = AvailableStems
                .Where(s => s.IsSelected)
                .Select(s => s.Name.ToLower())
                .ToArray();

            if (!selectedStems.Any())
            {
                StatusMessage = "Please select at least one stem type";
                return;
            }

            var parameters = new Dictionary<string, object>
            {
                { "target_bpm", TargetBpm },
                { "duration_seconds", DurationSeconds },
                { "style", Style }
            };

            if (!string.IsNullOrWhiteSpace(Prompt))
            {
                parameters.Add("prompt", Prompt);
            }

            var request = new CreateGenerationRequestDto(
                audioId,
                selectedStems,
                parameters
            );

            var result = await _apiClient.CreateGenerationRequestAsync(request);

            if (result != null)
            {
                GenerationRequest = result;
                StatusMessage = $"✓ Generation request created!\nID: {result.Id}\nStatus: {result.Status}\n\nThis will take 1-3 minutes per stem.";
            }
            else
            {
                StatusMessage = "Failed to create generation request";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
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
