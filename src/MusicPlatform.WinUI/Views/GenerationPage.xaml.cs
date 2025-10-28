using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using MusicPlatform.WinUI.ViewModels;

namespace MusicPlatform.WinUI.Views;

public sealed partial class GenerationPage : Page
{
    public GenerationViewModel ViewModel { get; }

    public GenerationPage()
    {
        this.InitializeComponent();
        ViewModel = App.Services.GetRequiredService<GenerationViewModel>();
        DataContext = ViewModel;
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        // No initial load required yet
    }
}
