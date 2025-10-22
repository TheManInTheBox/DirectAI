using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using System.Collections.ObjectModel;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// Helper for getting the current page across all ViewModels
/// </summary>
internal static class PageHelper
{
    public static Page? GetCurrentPage()
    {
        return Application.Current?.Windows?.FirstOrDefault()?.Page;
    }
}

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
    
    // Global collection for selected stems from multiple sources
    public static ObservableCollection<SelectedStemInfo> GlobalSelectedStems { get; } = new();

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
        NavigateToJobsCommand = new Command(async () => await NavigateToJobsAsync());
        ViewDetailsCommand = new Command<SourceMaterialItem>(async (item) => await ViewDetailsAsync(item));
        NavigateToGenerationCommand = new Command(async () =>
        {
            try
            {
                await NavigateToGenerationAsync();
            }
            catch (Exception ex)
            {
                var page = PageHelper.GetCurrentPage();
                if (page != null)
                {
                    await page.DisplayAlert("Error", 
                        $"Failed to navigate: {ex.Message}\n\nStack: {ex.StackTrace}", 
                        "OK");
                }
            }
        });
        
        // Subscribe to global collection changes to update UI
        GlobalSelectedStems.CollectionChanged += (s, e) => 
        {
            OnPropertyChanged(nameof(GlobalSelectedStemsCount));
            OnPropertyChanged(nameof(HasGlobalSelectedStems));
        };
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
    public ICommand NavigateToJobsCommand { get; }
    public ICommand ViewDetailsCommand { get; }
    public ICommand NavigateToGenerationCommand { get; }

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
    
    // Global stem selection properties for multi-source workflow
    public int GlobalSelectedStemsCount => GlobalSelectedStems.Count;
    public bool HasGlobalSelectedStems => GlobalSelectedStems.Any();

    public async Task InitializeAsync()
    {
        await LoadSourceLibraryAsync();
        await LoadGeneratedLibraryAsync();
    }

    /// <summary>
    /// Public method for handling dropped files from drag and drop
    /// </summary>
    public async Task HandleDroppedFilesAsync(IEnumerable<string> filePaths)
    {
        await UploadFilesAsync(filePaths);
    }

    private async Task UploadFilesAsync(IEnumerable<string> filePaths)
    {
        if (filePaths == null || !filePaths.Any())
        {
            Console.WriteLine("⚠️ No file paths provided to UploadFilesAsync");
            return;
        }

        try
        {
            Console.WriteLine($"📤 Starting upload of {filePaths.Count()} file(s)");
            IsUploading = true;
            var uploadedCount = 0;
            var totalFiles = filePaths.Count();
            
            foreach (var filePath in filePaths)
            {
                try
                {
                    Console.WriteLine($"📂 Processing file: {filePath}");
                    UploadStatus = $"Uploading {Path.GetFileName(filePath)} ({++uploadedCount}/{totalFiles})...";
                    
                    Console.WriteLine($"📖 Opening file stream...");
                    using var stream = File.OpenRead(filePath);
                    var fileName = Path.GetFileName(filePath);
                    
                    Console.WriteLine($"☁️ Calling API to upload {fileName}, size: {stream.Length} bytes");
                    var result = await _apiClient.UploadAudioAsync(stream, fileName);
                    
                    if (result != null)
                    {
                        // Automatically request analysis
                        await _apiClient.RequestAnalysisAsync(result.Id);
                    }
                }
                catch (Exception ex)
                {
                    var errorDetails = ex.InnerException != null 
                        ? $"{ex.Message} | Inner: {ex.InnerException.Message}"
                        : ex.Message;
                    UploadStatus = $"Error uploading {Path.GetFileName(filePath)}: {errorDetails}";
                    Console.WriteLine($"❌ UPLOAD ERROR: {ex}");
                    await Task.Delay(3000); // Show error longer
                }
            }

            UploadStatus = $"✓ Successfully uploaded {uploadedCount} file(s)! Processing analysis...";
            await Task.Delay(2000);
            UploadStatus = "📊 Files are being analyzed. They'll appear in Source Library once processing completes (1-2 min).";
            await Task.Delay(3000);
            UploadStatus = string.Empty;
            
            // Refresh source library
            await LoadSourceLibraryAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ UPLOAD ERROR (outer): {ex}");
            UploadStatus = $"Upload error: {ex.Message}";
            
            var page = PageHelper.GetCurrentPage();
            if (page != null)
            {
                await page.DisplayAlert("Upload Error", 
                    $"Failed to upload files:\n\n{ex.Message}\n\n{ex.InnerException?.Message}", 
                    "OK");
            }
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
            
            Console.WriteLine($"🔍 DEBUG: Loaded {audioFiles?.Count ?? 0} audio files from API");
            
            if (audioFiles == null) return;

            foreach (var file in audioFiles.OrderByDescending(f => f.UploadedAt))
            {
                Console.WriteLine($"🔍 DEBUG: Processing file: {file.Title}");
                Console.WriteLine($"🔍 DEBUG: AlbumArtworkUri: {file.AlbumArtworkUri}");
                
                // Get analysis for this file
                var analysis = await _apiClient.GetAnalysisAsync(file.Id);
                
                // Add original audio file
                var item = new SourceMaterialItem(file, analysis, _apiClient);
                item.PropertyChanged += OnSourceItemPropertyChanged;
                SourceMaterialLibrary.Add(item);
                
                Console.WriteLine($"🔍 DEBUG: Added audio file item. HasAlbumArtwork: {item.HasAlbumArtwork}");
            }
            
            Console.WriteLine($"🔍 DEBUG: Total items in SourceMaterialLibrary: {SourceMaterialLibrary.Count}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ ERROR loading source library: {ex.Message}");
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
                try
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
                catch (Exception stemEx)
                {
                    // Log but continue loading other requests
                    System.Diagnostics.Debug.WriteLine($"Error loading stems for request {request.Id}: {stemEx.Message}");
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
            item.StatusMessage = "🔬 Requesting analysis...";
            await _apiClient.RequestAnalysisAsync(item.AudioFileId);
            
            // Poll for progress
            item.StatusMessage = "⏳ Analyzing: Downloading audio...";
            await Task.Delay(2000);
            
            item.StatusMessage = "🎵 Analyzing: Separating stems (1-2 min)...";
            
            // Poll every 10 seconds for 3 minutes max
            var maxAttempts = 18; // 3 minutes
            var attempt = 0;
            var completed = false;
            
            while (attempt < maxAttempts && !completed)
            {
                await Task.Delay(10000); // Wait 10 seconds
                attempt++;
                
                try
                {
                    // Check if analysis is complete by fetching the file again
                    var audioFiles = await _apiClient.GetAllAudioFilesAsync();
                    var updatedFile = audioFiles?.FirstOrDefault(f => f.Id == item.AudioFileId);
                    
                    if (updatedFile?.Status == "Analyzed")
                    {
                        completed = true;
                        item.StatusMessage = "✅ Analysis complete! Click refresh to see results.";
                        await Task.Delay(3000);
                        item.StatusMessage = string.Empty;
                        
                        // Auto-refresh library
                        await LoadSourceLibraryAsync();
                        return;
                    }
                    
                    // Update progress message based on elapsed time
                    var elapsedSeconds = attempt * 10;
                    if (elapsedSeconds < 60)
                    {
                        item.StatusMessage = "🎵 Analyzing: Separating stems...";
                    }
                    else if (elapsedSeconds < 120)
                    {
                        item.StatusMessage = "🔍 Analyzing: Extracting features (BPM, key, chords)...";
                    }
                    else
                    {
                        item.StatusMessage = "📊 Analyzing: Finalizing results...";
                    }
                }
                catch
                {
                    // Continue polling even if status check fails
                }
            }
            
            if (!completed)
            {
                item.StatusMessage = "⏱️ Analysis taking longer than expected. Check back soon.";
                await Task.Delay(5000);
                item.StatusMessage = string.Empty;
            }
        }
        catch (Exception ex)
        {
            item.StatusMessage = $"❌ Error: {ex.Message}";
            await Task.Delay(5000);
            item.StatusMessage = string.Empty;
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
        
        var page = PageHelper.GetCurrentPage();
        if (page == null) return;
        
        if (!selectedItems.Any())
        {
            await page.DisplayAlert(
                "No Selection",
                "Please select analyzed source materials to generate stems.",
                "OK"
            );
            return;
        }

        var confirmed = await page.DisplayAlert(
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

            var successPage = PageHelper.GetCurrentPage();
            if (successPage != null)
            {
                await successPage.DisplayAlert(
                    "Batch Generation Started",
                    message,
                    "OK"
                );
            }

            // Exit selection mode and deselect all
            IsSelectionMode = false;
            DeselectAll();
        }
        catch (Exception ex)
        {
            var errorPage = PageHelper.GetCurrentPage();
            if (errorPage != null)
            {
                await errorPage.DisplayAlert(
                    "Error",
                    $"Error generating stems: {ex.Message}",
                    "OK"
                );
            }
        }
    }

    private async Task NavigateToJobsAsync()
    {
        await Shell.Current.GoToAsync("//JobsPage");
    }
    
    private async Task NavigateToGenerationAsync()
    {
        // Navigate directly to generation page with globally selected stems
        await Shell.Current.GoToAsync("generation");
    }

    private async Task ViewDetailsAsync(SourceMaterialItem item)
    {
        try
        {
            // Navigate to the detail page with the audio file ID
            var navigationParameter = new Dictionary<string, object>
            {
                { "AudioFileId", item.AudioFileId.ToString() }
            };
            
            await Shell.Current.GoToAsync("AudioFileDetailPage", navigationParameter);
        }
        catch (Exception ex)
        {
            // Navigation error - could show an alert here if needed
            System.Diagnostics.Debug.WriteLine($"Navigation error: {ex.Message}");
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
/// Source material library item (uploaded and analyzed audio, or separated stem)
/// </summary>
public class SourceMaterialItem : INotifyPropertyChanged
{
    private readonly AudioFileDto _audioFile;
    private readonly AnalysisResultDto? _analysis;
    private readonly StemDto? _stem;
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = string.Empty;
    private bool _isSelected = false;

    // Constructor for original audio file
    public SourceMaterialItem(AudioFileDto audioFile, AnalysisResultDto? analysis, MusicPlatformApiClient apiClient)
    {
        _audioFile = audioFile;
        _analysis = analysis;
        _stem = null;
        _apiClient = apiClient;
    }
    
    // Constructor for stem
    public SourceMaterialItem(AudioFileDto audioFile, AnalysisResultDto? analysis, StemDto stem, MusicPlatformApiClient apiClient)
    {
        _audioFile = audioFile;
        _analysis = analysis;
        _stem = stem;
        _apiClient = apiClient;
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public Guid AudioFileId => _audioFile.Id;
    public Guid? StemId => _stem?.Id;
    public bool IsStem => _stem != null;
    public string StemType => _stem?.Type ?? string.Empty;
    public string? NotationData => _stem?.NotationData;
    
    public string FileName => IsStem 
        ? $"{_audioFile.OriginalFileName} - {_stem!.Type}"
        : _audioFile.OriginalFileName;
        
    public string FileSizeFormatted => IsStem
        ? FormatFileSize(_stem!.FileSizeBytes)
        : FormatFileSize(_audioFile.SizeBytes);
        
    public string UploadedAt => IsStem
        ? (_stem!.AnalyzedAt?.ToString("g") ?? "Unknown")
        : _audioFile.UploadedAt.ToString("g");
    
    public bool IsAnalyzed => IsStem 
        ? _stem!.AnalysisStatus == "Completed"
        : _analysis?.Status == "Completed";
        
    public string AnalysisStatus => IsStem
        ? _stem!.AnalysisStatus
        : (_analysis?.Status ?? "Not Analyzed");
        
    public double? Bpm => IsStem
        ? _stem!.Bpm
        : _analysis?.Bpm;
        
    public string BpmFormatted => Bpm.HasValue ? $"{Bpm.Value:F1} BPM" : "Unknown";
    
    public string Key => IsStem
        ? _stem!.Key ?? "Unknown"
        : (_analysis?.Key ?? "Unknown");
        
    public string TimeSignature => IsStem
        ? _stem!.TimeSignature ?? "Unknown"
        : (_analysis?.TimeSignature ?? "Unknown");
        
    public bool HasNotation => IsStem && !string.IsNullOrEmpty(_stem!.NotationData);
    
    // Album artwork for card background
    public string? AlbumArtworkUri => _audioFile.AlbumArtworkUri;
    public bool HasAlbumArtwork => !string.IsNullOrWhiteSpace(_audioFile.AlbumArtworkUri);

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

    public string DisplayInfo
    {
        get
        {
            if (!IsAnalyzed)
                return $"{FileSizeFormatted} • {AnalysisStatus}";
                
            var info = $"{BpmFormatted} • {Key} • {TimeSignature}";
            
            if (IsStem)
            {
                info = $"🎵 {_stem!.Type} • {info}";
                if (HasNotation)
                    info += " • 📝 Notation";
            }
            
            return info;
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

            var page = PageHelper.GetCurrentPage();
            if (page != null)
            {
                await page.DisplayAlert(
                    "Download Complete",
                    $"Stem saved to:\n{filePath}",
                    "OK"
                );
            }
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

/// <summary>
/// Information about a selected stem for generation
/// </summary>
public class SelectedStemInfo
{
    public Guid StemId { get; set; }
    public string AudioFileName { get; set; } = string.Empty;
    public string StemType { get; set; } = string.Empty;
    public string DisplayName => $"{AudioFileName} - {StemType}";
}

#endregion
