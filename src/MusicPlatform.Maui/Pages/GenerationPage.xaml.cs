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

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        
        // Initialize with global stems when page appears
        try
        {
            await _viewModel.InitializeAsync();
        }
        catch (Exception ex)
        {
            await DisplayAlert("Error", 
                $"Failed to initialize generation page: {ex.Message}\n\nStack: {ex.StackTrace}", 
                "OK");
        }
    }

    public async Task InitializeWithAudioFileAsync(string audioFileId)
    {
        await _viewModel.InitializeAsync(audioFileId);
    }
}
