using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for viewing and downloading generated stems
/// </summary>
public class StemsViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = "Loading stems...";
    private bool _isLoading = true;
    private ObservableCollection<StemItemViewModel> _stems = new();

    public StemsViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        RefreshCommand = new Command(async () => await LoadAllStemsAsync());
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand RefreshCommand { get; }

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

    public ObservableCollection<StemItemViewModel> Stems
    {
        get => _stems;
        set => SetProperty(ref _stems, value);
    }

    public async Task InitializeAsync()
    {
        await LoadAllStemsAsync();
    }

    private async Task LoadAllStemsAsync()
    {
        try
        {
            IsLoading = true;
            StatusMessage = "Loading generated stems...";
            Stems.Clear();

            // Get all generation requests
            var requests = await _apiClient.GetAllGenerationRequestsAsync();

            if (requests == null || !requests.Any())
            {
                StatusMessage = "No generated stems found. Generate some stems first!";
                return;
            }

            // For each completed request, get the stems
            var completedRequests = requests.Where(r => r.Status == "Completed").ToList();

            if (!completedRequests.Any())
            {
                StatusMessage = "No completed stems yet. Generation in progress...";
                return;
            }

            foreach (var request in completedRequests)
            {
                var stems = await _apiClient.GetGeneratedStemsAsync(request.Id);
                if (stems != null)
                {
                    foreach (var stem in stems)
                    {
                        Stems.Add(new StemItemViewModel(stem, _apiClient));
                    }
                }
            }

            StatusMessage = Stems.Any() 
                ? $"Found {Stems.Count} generated stem(s)" 
                : "No stems found";
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error loading stems: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
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
/// ViewModel for individual stem item
/// </summary>
public class StemItemViewModel : INotifyPropertyChanged
{
    private readonly GeneratedStemDto _stem;
    private readonly MusicPlatformApiClient _apiClient;
    private bool _isDownloading = false;
    private string _statusMessage = string.Empty;

    public StemItemViewModel(GeneratedStemDto stem, MusicPlatformApiClient apiClient)
    {
        _stem = stem;
        _apiClient = apiClient;
        DownloadCommand = new Command(async () => await DownloadStemAsync());
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand DownloadCommand { get; }

    public Guid Id => _stem.Id;
    public string StemType => _stem.StemType.ToUpper();
    public string FileSizeFormatted => FormatFileSize(_stem.FileSizeBytes);
    public string Duration => _stem.DurationSeconds > 0
        ? $"{_stem.DurationSeconds:F1}s" 
        : "Unknown";
    public string CreatedAt => _stem.CreatedAt.ToString("g");
    
    // Metadata properties for display
    public string? AlbumArtworkUri => _stem.AlbumArtworkUri;
    public string DisplayTitle => _stem.AudioFileTitle ?? "Unknown Track";
    public string DisplayArtist => _stem.AudioFileArtist ?? "Unknown Artist";
    public string DisplayAlbum => _stem.AudioFileAlbum ?? string.Empty;
    public bool HasAlbumArtwork => !string.IsNullOrWhiteSpace(_stem.AlbumArtworkUri);
    public bool HasMetadata => !string.IsNullOrWhiteSpace(_stem.AudioFileTitle) || 
                               !string.IsNullOrWhiteSpace(_stem.AudioFileArtist);

    public bool IsDownloading
    {
        get => _isDownloading;
        set
        {
            _isDownloading = value;
            OnPropertyChanged();
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

    private async Task DownloadStemAsync()
    {
        try
        {
            IsDownloading = true;
            StatusMessage = "Downloading...";

            var stream = await _apiClient.DownloadStemAsync(_stem.Id);
            if (stream == null)
            {
                StatusMessage = "Download failed";
                return;
            }

            // Save to downloads folder
            var fileName = $"{_stem.StemType}_{_stem.Id}.wav";
            var downloadsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            var filePath = Path.Combine(downloadsPath, "MusicPlatform", fileName);

            Directory.CreateDirectory(Path.GetDirectoryName(filePath)!);

            using (var fileStream = File.Create(filePath))
            {
                await stream.CopyToAsync(fileStream);
            }

            StatusMessage = $"✓ Saved to {filePath}";

            // Show alert
            await Application.Current!.Windows[0].Page!.DisplayAlert(
                "Download Complete",
                $"Stem saved to:\n{filePath}",
                "OK"
            );
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
        }
        finally
        {
            IsDownloading = false;
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
