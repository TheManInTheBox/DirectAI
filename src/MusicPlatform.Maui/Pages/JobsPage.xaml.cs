using MusicPlatform.Maui.ViewModels;
using MusicPlatform.Maui.Services;

namespace MusicPlatform.Maui.Pages;

public partial class JobsPage : ContentPage
{
    public JobsPage(MusicPlatformApiClient apiClient)
    {
        InitializeComponent();
        BindingContext = new JobsViewModel(apiClient);
    }
}
