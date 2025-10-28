using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using MusicPlatform.WinUI.ViewModels;

namespace MusicPlatform.WinUI.Views;

public sealed partial class DashboardPage : Page
{
    public DashboardViewModel ViewModel { get; }

    public DashboardPage()
    {
        this.InitializeComponent();
        ViewModel = App.Services.GetRequiredService<DashboardViewModel>();
        DataContext = ViewModel;
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        ViewModel.LoadStatsCommand.Execute(null);
    }

    private void OnNavigateToAudioLibrary(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        if (Frame?.Parent is NavigationView navView)
        {
            // Find the Audio Library navigation item and select it
            foreach (var item in navView.MenuItems)
            {
                if (item is NavigationViewItem navItem && navItem.Tag?.ToString() == "AudioLibrary")
                {
                    navView.SelectedItem = navItem;
                    break;
                }
            }
        }
    }

    private void OnNavigateToGeneration(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        if (Frame?.Parent is NavigationView navView)
        {
            // Find the Generation navigation item and select it
            foreach (var item in navView.MenuItems)
            {
                if (item is NavigationViewItem navItem && navItem.Tag?.ToString() == "Generation")
                {
                    navView.SelectedItem = navItem;
                    break;
                }
            }
        }
    }
}
