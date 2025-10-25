using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

public partial class MixingPage : ContentPage
{
    public MixingPage(MixingViewModel viewModel)
    {
        InitializeComponent();
        BindingContext = viewModel;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        
        if (BindingContext is MixingViewModel viewModel)
        {
            await viewModel.InitializeAsync();
        }
    }
}
