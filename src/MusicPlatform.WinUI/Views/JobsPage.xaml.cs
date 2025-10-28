using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using MusicPlatform.WinUI.ViewModels;

namespace MusicPlatform.WinUI.Views;

public sealed partial class JobsPage : Page
{
    public JobsViewModel ViewModel { get; }

    public JobsPage()
    {
        this.InitializeComponent();
        ViewModel = App.Services.GetRequiredService<JobsViewModel>();
        DataContext = ViewModel;
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        ViewModel.LoadJobsCommand.Execute(null);
        ViewModel.StartPeriodicRefresh();
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        base.OnNavigatedFrom(e);
        ViewModel.StopPeriodicRefresh();
    }
}
