using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using MusicPlatform.WinUI.ViewModels;
using Windows.Storage.Pickers;
using Windows.Storage;
using Windows.Storage.Streams;
using WinRT.Interop;
using System.Runtime.InteropServices.WindowsRuntime;

namespace MusicPlatform.WinUI.Views;

public sealed partial class AudioLibraryPage : Page
{
    public AudioLibraryViewModel ViewModel { get; }

    public AudioLibraryPage()
    {
        this.InitializeComponent();
        ViewModel = App.Services.GetRequiredService<AudioLibraryViewModel>();
        DataContext = ViewModel;
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        ViewModel.LoadAudioFilesCommand.Execute(null);
    }

    private async void OnUploadClick(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        var picker = new FileOpenPicker
        {
            ViewMode = PickerViewMode.List,
            SuggestedStartLocation = PickerLocationId.MusicLibrary
        };

        picker.FileTypeFilter.Add(".mp3");
        picker.FileTypeFilter.Add(".wav");
        picker.FileTypeFilter.Add(".flac");
        picker.FileTypeFilter.Add(".m4a");

        // Initialize with window handle
        var hwnd = WindowNative.GetWindowHandle(App.MainWindow);
        InitializeWithWindow.Initialize(picker, hwnd);

        var files = await picker.PickMultipleFilesAsync();
        if (files == null || files.Count == 0) return;

        foreach (StorageFile file in files)
        {
            using IRandomAccessStream ras = await file.OpenReadAsync();
            using var stream = ras.AsStreamForRead();
            await ViewModel.UploadAndAnalyzeAsync(stream, file.Name);
        }

        // Refresh list after uploads
        ViewModel.LoadAudioFilesCommand.Execute(null);
    }
}
