using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

[QueryProperty(nameof(AudioFileId), "AudioFileId")]
public partial class AudioFileDetailPage : ContentPage
{
    private readonly AudioFileDetailViewModel _viewModel;
    private string? _audioFileId;

    public string? AudioFileId
    {
        get => _audioFileId;
        set
        {
            _audioFileId = value;
            if (_viewModel != null && !string.IsNullOrEmpty(value))
            {
                _viewModel.SetAudioFileId(value);
            }
        }
    }

    public AudioFileDetailPage(AudioFileDetailViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        BindingContext = viewModel;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        
        if (_viewModel != null)
        {
            await _viewModel.InitializeAsync();
        }
    }
}
