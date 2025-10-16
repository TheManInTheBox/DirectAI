using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.ViewModels;

/// <summary>
/// ViewModel for the audio file upload page
/// </summary>
public class UploadViewModel : INotifyPropertyChanged
{
    private readonly MusicPlatformApiClient _apiClient;
    private string _statusMessage = string.Empty;
    private double _uploadProgress = 0;
    private bool _isUploading = false;
    private string? _selectedFileName;
    private AudioFileDto? _uploadedFile;

    public UploadViewModel(MusicPlatformApiClient apiClient)
    {
        _apiClient = apiClient;
        SelectFileCommand = new Command(async () => await SelectFileAsync());
        UploadFileCommand = new Command(async () => await UploadFileAsync(), () => CanUpload);
        ViewAnalysisCommand = new Command(async () => await ViewAnalysisAsync(), () => UploadedFile != null);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public ICommand SelectFileCommand { get; }
    public ICommand UploadFileCommand { get; }
    public ICommand ViewAnalysisCommand { get; }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public double UploadProgress
    {
        get => _uploadProgress;
        set => SetProperty(ref _uploadProgress, value);
    }

    public bool IsUploading
    {
        get => _isUploading;
        set
        {
            if (SetProperty(ref _isUploading, value))
            {
                ((Command)UploadFileCommand).ChangeCanExecute();
            }
        }
    }

    public string? SelectedFileName
    {
        get => _selectedFileName;
        set
        {
            if (SetProperty(ref _selectedFileName, value))
            {
                ((Command)UploadFileCommand).ChangeCanExecute();
            }
        }
    }

    public AudioFileDto? UploadedFile
    {
        get => _uploadedFile;
        set
        {
            if (SetProperty(ref _uploadedFile, value))
            {
                ((Command)ViewAnalysisCommand).ChangeCanExecute();
            }
        }
    }

    public bool CanUpload => !IsUploading && !string.IsNullOrEmpty(SelectedFileName);

    private FileResult? _selectedFile;

    private async Task SelectFileAsync()
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
                PickerTitle = "Select an MP3 file",
                FileTypes = customFileType
            };

            _selectedFile = await FilePicker.Default.PickAsync(options);

            if (_selectedFile != null)
            {
                SelectedFileName = _selectedFile.FileName;
                StatusMessage = $"Selected: {_selectedFile.FileName}";
                UploadProgress = 0;
                UploadedFile = null;
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error selecting file: {ex.Message}";
        }
    }

    private async Task UploadFileAsync()
    {
        if (_selectedFile == null) return;

        try
        {
            IsUploading = true;
            StatusMessage = "Uploading...";
            UploadProgress = 0;

            using var stream = await _selectedFile.OpenReadAsync();
            
            var progress = new Progress<double>(value =>
            {
                UploadProgress = value;
            });

            var result = await _apiClient.UploadAudioAsync(
                stream,
                _selectedFile.FileName,
                progress
            );

            if (result != null)
            {
                UploadedFile = result;
                UploadProgress = 100;
                StatusMessage = $"✓ Upload complete! File ID: {result.Id}";
                
                // Automatically request analysis
                StatusMessage += "\nRequesting analysis...";
                await RequestAnalysisAsync(result.Id);
            }
            else
            {
                StatusMessage = "Upload failed: No response from server";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Upload error: {ex.Message}";
            UploadProgress = 0;
        }
        finally
        {
            IsUploading = false;
        }
    }

    private async Task RequestAnalysisAsync(Guid audioFileId)
    {
        try
        {
            var analysisResult = await _apiClient.RequestAnalysisAsync(audioFileId);
            if (analysisResult != null)
            {
                StatusMessage += $"\n✓ Analysis requested. Status: {analysisResult.Status}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage += $"\nAnalysis request failed: {ex.Message}";
        }
    }

    private async Task ViewAnalysisAsync()
    {
        if (UploadedFile == null) return;

        // Navigate to Analysis tab
        await Shell.Current.GoToAsync("//AnalysisPage");
        
        // Find the Analysis page and initialize it
        var analysisPage = Shell.Current.CurrentPage as MusicPlatform.Maui.Pages.AnalysisPage;
        if (analysisPage != null)
        {
            await analysisPage.InitializeWithAudioFileAsync(UploadedFile.Id.ToString());
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
