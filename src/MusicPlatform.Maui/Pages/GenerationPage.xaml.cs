using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

public partial class GenerationPage : ContentPage
{
    private readonly GenerationViewModel _viewModel;

    public GenerationPage(GenerationViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        BindingContext = _viewModel;
    }

    public async Task InitializeWithAudioFileAsync(string audioFileId)
    {
        await _viewModel.InitializeAsync(audioFileId);
    }
}
