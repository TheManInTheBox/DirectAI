using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MusicPlatform.WinUI.Models;
using MusicPlatform.WinUI.Services;
using System.Collections.ObjectModel;
using System.IO;

namespace MusicPlatform.WinUI.ViewModels;

public partial class AudioLibraryViewModel : ObservableObject
{
    private readonly MusicPlatformApiClient _apiClient;

    [ObservableProperty]
    private ObservableCollection<AudioFileDto> _audioFiles = new();

    [ObservableProperty]
    private bool _isLoading;

    public AudioLibraryViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
    }

    [RelayCommand]
    private async Task LoadAudioFilesAsync()
    {
        await LoadAudioFilesInternalAsync();
    }

    public async Task LoadAudioFilesInternalAsync()
    {
        IsLoading = true;
        try
        {
            var files = await _apiClient.GetAllAudioFilesAsync();
            AudioFiles.Clear();
            if (files != null)
            {
                foreach (var file in files.OrderByDescending(f => f.UploadedAt))
                {
                    AudioFiles.Add(file);
                }
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error loading audio files: {ex.Message}");
        }
        finally
        {
            IsLoading = false;
        }
    }

    public async Task UploadAndAnalyzeAsync(Stream stream, string fileName)
    {
        try
        {
            var uploaded = await _apiClient.UploadAudioAsync(stream, fileName);
            if (uploaded != null)
            {
                // Add to top of list
                AudioFiles.Insert(0, uploaded);

                // Trigger analysis (which includes stem separation in pipeline)
                _ = _apiClient.RequestAnalysisAsync(uploaded.Id);
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error uploading/analyzing audio: {ex.Message}");
        }
    }

    [RelayCommand]
    private async Task DeleteAudioFileAsync(Guid audioFileId)
    {
        try
        {
            await _apiClient.DeleteAudioFileAsync(audioFileId);
            var file = AudioFiles.FirstOrDefault(f => f.Id == audioFileId);
            if (file != null)
            {
                AudioFiles.Remove(file);
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error deleting audio file: {ex.Message}");
        }
    }
}
