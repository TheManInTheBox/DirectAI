using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MusicPlatform.WinUI.Models;
using MusicPlatform.WinUI.Services;

namespace MusicPlatform.WinUI.ViewModels;

public partial class GenerationViewModel : ObservableObject
{
    private readonly MusicPlatformApiClient _apiClient;

    [ObservableProperty]
    private string _prompt = "";

    [ObservableProperty]
    private double _duration = 30;

    [ObservableProperty]
    private string _key = "C";

    [ObservableProperty]
    private int _bpm = 120;

    [ObservableProperty]
    private double _temperature = 1.0;

    [ObservableProperty]
    private int _topK = 250;

    [ObservableProperty]
    private double _topP = 0.0;

    [ObservableProperty]
    private bool _isGenerating;

    [ObservableProperty]
    private string _statusMessage = "";

    public GenerationViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
    }

    [RelayCommand]
    private async Task GenerateAsync()
    {
        // Minimal flow: submit generation for the most recent audio file using provided parameters
        if (string.IsNullOrWhiteSpace(Prompt))
        {
            StatusMessage = "Enter a prompt to generate.";
            return;
        }

        IsGenerating = true;
        StatusMessage = "Submitting generation request...";

        try
        {
            // Select the most recently uploaded audio file as the conditioning source
            var audioFiles = await _apiClient.GetAllAudioFilesAsync();
            var audio = audioFiles?
                .OrderByDescending(a => a.UploadedAt)
                .FirstOrDefault();

            if (audio == null)
            {
                StatusMessage = "No audio files found. Upload an audio file first.";
                return;
            }

            // Default to generating a full track or generic stem (server enum accepts "Other")
            var request = new CreateGenerationRequestDto(
                AudioFileId: audio.Id,
                TargetStems: new[] { "Other" },
                Parameters: new
                {
                    TargetBpm = (float?)(Bpm > 0 ? Bpm : null),
                    DurationSeconds = (float)Duration,
                    Prompt = Prompt,
                    Temperature = (float)Temperature,
                    Key = string.IsNullOrWhiteSpace(Key) ? null : Key,
                    TopK = TopK,
                    TopP = (float)TopP
                }
            );

            var result = await _apiClient.CreateGenerationRequestAsync(request);
            if (result != null)
            {
                StatusMessage = $"Generation created: {result.Id}";
            }
            else
            {
                StatusMessage = "Generation request failed (no response).";
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
}
