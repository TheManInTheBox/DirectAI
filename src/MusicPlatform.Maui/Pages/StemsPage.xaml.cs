using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

public partial class StemsPage : ContentPage
{
    private readonly StemsViewModel _viewModel;

    public StemsPage(StemsViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        BindingContext = _viewModel;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await _viewModel.InitializeAsync();
    }
}
