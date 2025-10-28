using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using MusicPlatform.WinUI.Services;

namespace MusicPlatform.WinUI.ViewModels;

public partial class DashboardViewModel : ObservableObject
{
    private readonly MusicPlatformApiClient _apiClient;

    private int _audioFilesCount;
    public int AudioFilesCount
    {
        get => _audioFilesCount;
        set => SetProperty(ref _audioFilesCount, value);
    }

    private int _stemsCount;
    public int StemsCount
    {
        get => _stemsCount;
        set => SetProperty(ref _stemsCount, value);
    }

    private int _generationsCount;
    public int GenerationsCount
    {
        get => _generationsCount;
        set => SetProperty(ref _generationsCount, value);
    }

    private bool _isLoading;
    public bool IsLoading
    {
        get => _isLoading;
        set => SetProperty(ref _isLoading, value);
    }

    private DateTime? _lastUpdated;
    public DateTime? LastUpdated
    {
        get => _lastUpdated;
        set => SetProperty(ref _lastUpdated, value);
    }

    private string? _errorMessage;
    public string? ErrorMessage
    {
        get => _errorMessage;
        set => SetProperty(ref _errorMessage, value);
    }

    public DashboardViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
    }

    [RelayCommand]
    private async Task LoadStatsAsync()
    {
        await LoadStatsInternalAsync();
    }

    public async Task LoadStatsInternalAsync()
    {
        IsLoading = true;
        ErrorMessage = null;
        try
        {
            var audioFiles = await _apiClient.GetAllAudioFilesAsync();
            AudioFilesCount = audioFiles?.Count ?? 0;

            var generations = await _apiClient.GetAllGenerationRequestsAsync();
            GenerationsCount = generations?.Count ?? 0;

            var stemStats = await _apiClient.GetStemStatisticsAsync();
            StemsCount = stemStats?.TotalStems ?? 0;

            LastUpdated = DateTime.Now;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error loading stats: {ex.Message}");
            ErrorMessage = ex.Message;
        }
        finally
        {
            IsLoading = false;
        }
    }
}
