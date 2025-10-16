using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// Main ViewModel with drag-and-drop upload and library carousels
/// </summary>
public class MainViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private bool _isUploading = false;
    private string _uploadStatus = string.Empty;
    private bool _isLoadingSourceLibrary = false;
    private bool _isLoadingGeneratedLibrary = false;
    private bool _isSelectionMode = false;
    private int _selectedItemsCount = 0;

    public MainViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        
        SourceMaterialLibrary = new ObservableCollection<SourceMaterialItem>();
        GeneratedMusicLibrary = new ObservableCollection<GeneratedMusicItem>();
        
        UploadFilesCommand = new Command<IEnumerable<string>>(async (files) => await UploadFilesAsync(files));
        SelectFilesCommand = new Command(async () => await SelectFilesAsync());
        RefreshSourceLibraryCommand = new Command(async () => await LoadSourceLibraryAsync());
        RefreshGeneratedLibraryCommand = new Command(async () => await LoadGeneratedLibraryAsync());
        AnalyzeItemCommand = new Command<SourceMaterialItem>(async (item) => await AnalyzeItemAsync(item));
        GenerateFromItemCommand = new Command<SourceMaterialItem>(async (item) => await GenerateFromItemAsync(item));
        DownloadStemCommand = new Command<GeneratedMusicItem>(async (item) => await DownloadStemAsync(item));
        
        ToggleSelectionModeCommand = new Command(() => ToggleSelectionMode());
        SelectAllCommand = new Command(() => SelectAll());
        DeselectAllCommand = new Command(() => DeselectAll());
        GenerateFromSelectedCommand = new Command(async () => await GenerateFromSelectedAsync(), () => SelectedItemsCount > 0);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand UploadFilesCommand { get; }
    public ICommand SelectFilesCommand { get; }
    public ICommand RefreshSourceLibraryCommand { get; }
    public ICommand RefreshGeneratedLibraryCommand { get; }
    public ICommand AnalyzeItemCommand { get; }
    public ICommand GenerateFromItemCommand { get; }
    public ICommand DownloadStemCommand { get; }
    public ICommand ToggleSelectionModeCommand { get; }
    public ICommand SelectAllCommand { get; }
    public ICommand DeselectAllCommand { get; }
    public ICommand GenerateFromSelectedCommand { get; }

    public ObservableCollection<SourceMaterialItem> SourceMaterialLibrary { get; }
    public ObservableCollection<GeneratedMusicItem> GeneratedMusicLibrary { get; }

    public bool IsUploading
    {
        get => _isUploading;
        set => SetProperty(ref _isUploading, value);
    }

    public string UploadStatus
    {
        get => _uploadStatus;
        set => SetProperty(ref _uploadStatus, value);
    }

    public bool IsLoadingSourceLibrary
    {
        get => _isLoadingSourceLibrary;
        set => SetProperty(ref _isLoadingSourceLibrary, value);
    }

    public bool IsLoadingGeneratedLibrary
    {
        get => _isLoadingGeneratedLibrary;
        set => SetProperty(ref _isLoadingGeneratedLibrary, value);
    }

    public bool IsSelectionMode
    {
        get => _isSelectionMode;
        set => SetProperty(ref _isSelectionMode, value);
    }

    public int SelectedItemsCount
    {
        get => _selectedItemsCount;
        set
        {
            SetProperty(ref _selectedItemsCount, value);
            ((Command)GenerateFromSelectedCommand).ChangeCanExecute();
        }
    }

    public async Task InitializeAsync()
    {
        await LoadSourceLibraryAsync();
        await LoadGeneratedLibraryAsync();
    }

    private async Task UploadFilesAsync(IEnumerable<string> filePaths)
    {
        if (filePaths == null || !filePaths.Any()) return;

        try
        {
            IsUploading = true;
            var uploadedCount = 0;
            var totalFiles = filePaths.Count();
            
            foreach (var filePath in filePaths)
            {
                try
                {
                    UploadStatus = $"Uploading {Path.GetFileName(filePath)} ({++uploadedCount}/{totalFiles})...";
                    
                    using var stream = File.OpenRead(filePath);
                    var fileName = Path.GetFileName(filePath);
                    
                    var result = await _apiClient.UploadAudioAsync(stream, fileName);
                    
                    if (result != null)
                    {
                        // Automatically request analysis
                        await _apiClient.RequestAnalysisAsync(result.Id);
                    }
                }
                catch (Exception ex)
                {
                    UploadStatus = $"Error uploading {Path.GetFileName(filePath)}: {ex.Message}";
                    await Task.Delay(2000); // Show error briefly
                }
            }

            UploadStatus = $"✓ Successfully uploaded {uploadedCount} file(s)!";
            await Task.Delay(2000);
            UploadStatus = string.Empty;
            
            // Refresh source library
            await LoadSourceLibraryAsync();
        }
        catch (Exception ex)
        {
            UploadStatus = $"Upload error: {ex.Message}";
        }
        finally
        {
            IsUploading = false;
        }
    }

    private async Task SelectFilesAsync()
    {
        try
        {
            var customFileType = new FilePickerFileType(
                new Dictionary<DevicePlatform, IEnumerable<string>>
                {
                    { DevicePlatform.iOS, new[] { "public.mp3" } },
                    { DevicePlatform.Android, new[] { "audio/mpeg" } },
                    { DevicePlatform.WinUI, new[] { ".mp3" } },
                    { DevicePlatform.macOS, new[] { "mp3" } },
                }
            );

            var options = new PickOptions
            {
                PickerTitle = "Select MP3 files",
                FileTypes = customFileType
            };

            var results = await FilePicker.Default.PickMultipleAsync(options);
            
            if (results != null && results.Any())
            {
                var filePaths = results.Select(r => r.FullPath).ToList();
                await UploadFilesAsync(filePaths);
            }
        }
        catch (Exception ex)
        {
            UploadStatus = $"File selection error: {ex.Message}";
        }
    }

    private async Task LoadSourceLibraryAsync()
    {
        try
        {
            IsLoadingSourceLibrary = true;
            SourceMaterialLibrary.Clear();

            var audioFiles = await _apiClient.GetAllAudioFilesAsync();
            
            if (audioFiles == null) return;

            foreach (var file in audioFiles.OrderByDescending(f => f.UploadedAt))
            {
                // Get analysis for this file
                var analysis = await _apiClient.GetAnalysisAsync(file.Id);
                
                var item = new SourceMaterialItem(file, analysis, _apiClient);
                item.PropertyChanged += OnSourceItemPropertyChanged;
                SourceMaterialLibrary.Add(item);
            }
        }
        catch (Exception ex)
        {
            UploadStatus = $"Error loading source library: {ex.Message}";
        }
        finally
        {
            IsLoadingSourceLibrary = false;
        }
    }

    private async Task LoadGeneratedLibraryAsync()
    {
        try
        {
            IsLoadingGeneratedLibrary = true;
            GeneratedMusicLibrary.Clear();

            var requests = await _apiClient.GetAllGenerationRequestsAsync();
            
            if (requests == null) return;

            var completedRequests = requests
                .Where(r => r.Status == "Completed")
                .OrderByDescending(r => r.CompletedAt);

            foreach (var request in completedRequests)
            {
                var stems = await _apiClient.GetGeneratedStemsAsync(request.Id);
                
                if (stems != null)
                {
                    foreach (var stem in stems)
                    {
                        GeneratedMusicLibrary.Add(new GeneratedMusicItem(stem, request, _apiClient));
                    }
                }
            }
        }
        catch (Exception ex)
        {
            UploadStatus = $"Error loading generated library: {ex.Message}";
        }
        finally
        {
            IsLoadingGeneratedLibrary = false;
        }
    }

    private async Task AnalyzeItemAsync(SourceMaterialItem item)
    {
        if (item == null) return;

        try
        {
            item.StatusMessage = "Requesting analysis...";
            await _apiClient.RequestAnalysisAsync(item.AudioFileId);
            item.StatusMessage = "Analysis requested. Refresh library in 30-60 seconds.";
        }
        catch (Exception ex)
        {
            item.StatusMessage = $"Error: {ex.Message}";
        }
    }

    private async Task GenerateFromItemAsync(SourceMaterialItem item)
    {
        if (item == null || !item.IsAnalyzed) return;

        // Show generation dialog
        await Application.Current!.Windows[0].Page!.DisplayAlert(
            "Generate Stems",
            $"Generate AI stems from '{item.FileName}'?\n\nThis will create guitar, bass, and drums stems.\n\nProcessing time: 1-3 minutes per stem.",
            "OK"
        );

        try
        {
            item.StatusMessage = "Creating generation request...";
            
            var request = new CreateGenerationRequestDto(
                item.AudioFileId,
                new[] { "guitar", "bass", "drums" },
                new Dictionary<string, object>
                {
                    { "target_bpm", item.Bpm ?? 120.0 },
                    { "duration_seconds", 10.0 },
                    { "style", "rock" }
                }
            );

            var result = await _apiClient.CreateGenerationRequestAsync(request);
            
            if (result != null)
            {
                item.StatusMessage = $"✓ Generation started! Check Generated Library in 3-5 minutes.";
            }
        }
        catch (Exception ex)
        {
            item.StatusMessage = $"Error: {ex.Message}";
        }
    }

    private async Task DownloadStemAsync(GeneratedMusicItem item)
    {
        if (item == null) return;
        await item.DownloadAsync();
    }

    private void ToggleSelectionMode()
    {
        IsSelectionMode = !IsSelectionMode;
        
        if (!IsSelectionMode)
        {
            // Deselect all when leaving selection mode
            DeselectAll();
        }
    }

    private void SelectAll()
    {
        foreach (var item in SourceMaterialLibrary)
        {
            if (item.IsAnalyzed)
            {
                item.IsSelected = true;
            }
        }
        UpdateSelectedCount();
    }

    private void DeselectAll()
    {
        foreach (var item in SourceMaterialLibrary)
        {
            item.IsSelected = false;
        }
        UpdateSelectedCount();
    }

    private void UpdateSelectedCount()
    {
        SelectedItemsCount = SourceMaterialLibrary.Count(item => item.IsSelected);
    }

    private void OnSourceItemPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(SourceMaterialItem.IsSelected))
        {
            UpdateSelectedCount();
        }
    }

    private async Task GenerateFromSelectedAsync()
    {
        var selectedItems = SourceMaterialLibrary.Where(item => item.IsSelected && item.IsAnalyzed).ToList();
        
        if (!selectedItems.Any())
        {
            await Application.Current!.MainPage!.DisplayAlert(
                "No Selection",
                "Please select analyzed source materials to generate stems.",
                "OK"
            );
            return;
        }

        var confirmed = await Application.Current!.MainPage!.DisplayAlert(
            "Generate Stems",
            $"Generate AI stems from {selectedItems.Count} selected file(s)?\n\nThis will create guitar, bass, and drums stems for each file.\n\nProcessing time: 1-3 minutes per stem.",
            "Generate",
            "Cancel"
        );

        if (!confirmed) return;

        try
        {
            var successCount = 0;
            var errorCount = 0;

            foreach (var item in selectedItems)
            {
                try
                {
                    item.StatusMessage = "Creating generation request...";
                    
                    var request = new CreateGenerationRequestDto(
                        item.AudioFileId,
                        new[] { "guitar", "bass", "drums" },
                        new Dictionary<string, object>
                        {
                            { "target_bpm", item.Bpm ?? 120.0 },
                            { "duration_seconds", 10.0 },
                            { "style", "rock" }
                        }
                    );

                    var result = await _apiClient.CreateGenerationRequestAsync(request);
                    
                    if (result != null)
                    {
                        item.StatusMessage = "✓ Generation started!";
                        successCount++;
                    }
                }
                catch (Exception ex)
                {
                    item.StatusMessage = $"Error: {ex.Message}";
                    errorCount++;
                }
            }

            // Show summary
            var message = $"Started generation for {successCount} file(s).";
            if (errorCount > 0)
            {
                message += $"\n{errorCount} failed.";
            }
            message += "\n\nCheck Generated Library in 3-5 minutes.";

            await Application.Current!.MainPage!.DisplayAlert(
                "Batch Generation Started",
                message,
                "OK"
            );

            // Exit selection mode and deselect all
            IsSelectionMode = false;
            DeselectAll();
        }
        catch (Exception ex)
        {
            await Application.Current!.MainPage!.DisplayAlert(
                "Error",
                $"Error generating stems: {ex.Message}",
                "OK"
            );
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

#region Item Models

/// <summary>
/// Source material library item (uploaded and analyzed audio)
/// </summary>
public class SourceMaterialItem : INotifyPropertyChanged
{
    private readonly AudioFileDto _audioFile;
    private readonly AnalysisResultDto? _analysis;
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = string.Empty;
    private bool _isSelected = false;

    public SourceMaterialItem(AudioFileDto audioFile, AnalysisResultDto? analysis, MusicPlatformApiClient apiClient)
    {
        _audioFile = audioFile;
        _analysis = analysis;
        _apiClient = apiClient;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public Guid AudioFileId => _audioFile.Id;
    public string FileName => _audioFile.OriginalFileName;
    public string FileSizeFormatted => FormatFileSize(_audioFile.SizeBytes);
    public string UploadedAt => _audioFile.UploadedAt.ToString("g");
    
    public bool IsAnalyzed => _analysis?.Status == "Completed";
    public string AnalysisStatus => _analysis?.Status ?? "Not Analyzed";
    public double? Bpm => _analysis?.Bpm;
    public string BpmFormatted => Bpm.HasValue ? $"{Bpm.Value:F1} BPM" : "Unknown";
    public string Key => _analysis?.Key ?? "Unknown";
    public string TimeSignature => _analysis?.TimeSignature ?? "Unknown";

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            _isSelected = value;
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

    public string DisplayInfo => IsAnalyzed 
        ? $"{BpmFormatted} • {Key} • {TimeSignature}"
        : $"{FileSizeFormatted} • {AnalysisStatus}";

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

/// <summary>
/// Generated music library item (AI-generated stems)
/// </summary>
public class GeneratedMusicItem : INotifyPropertyChanged
{
    private readonly GeneratedStemDto _stem;
    private readonly GenerationRequestDto _request;
    private readonly MusicPlatformApiClient _apiClient;
    private bool _isDownloading = false;
    private string _statusMessage = string.Empty;

    public GeneratedMusicItem(GeneratedStemDto stem, GenerationRequestDto request, MusicPlatformApiClient apiClient)
    {
        _stem = stem;
        _request = request;
        _apiClient = apiClient;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public Guid StemId => _stem.Id;
    public string StemType => char.ToUpper(_stem.StemType[0]) + _stem.StemType.Substring(1);
    public string FileSizeFormatted => FormatFileSize(_stem.FileSizeBytes);
    public string Duration => _stem.DurationSeconds.HasValue ? $"{_stem.DurationSeconds.Value:F1}s" : "Unknown";
    public string CreatedAt => _stem.CreatedAt.ToString("g");
    public string DisplayInfo => $"{Duration} • {FileSizeFormatted} • {CreatedAt}";

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

    public async Task DownloadAsync()
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

            var fileName = $"{_stem.StemType}_{_stem.Id}.wav";
            var downloadsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            var filePath = Path.Combine(downloadsPath, "MusicPlatform", fileName);

            Directory.CreateDirectory(Path.GetDirectoryName(filePath)!);

            using (var fileStream = File.Create(filePath))
            {
                await stream.CopyToAsync(fileStream);
            }

            StatusMessage = $"✓ Downloaded";

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

#endregion
