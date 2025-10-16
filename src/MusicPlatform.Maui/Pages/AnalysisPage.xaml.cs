using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

public partial class AnalysisPage : ContentPage
{
    private readonly AnalysisViewModel _viewModel;

    public AnalysisPage(AnalysisViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        BindingContext = _viewModel;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        
        // Get audio file ID from navigation parameters
        if (BindingContext is AnalysisViewModel vm)
        {
            // This will be set via navigation parameters
            // For now, we'll handle it in the navigation logic
        }
    }

    public async Task InitializeWithAudioFileAsync(string audioFileId)
    {
        await _viewModel.InitializeAsync(audioFileId);
    }
}
