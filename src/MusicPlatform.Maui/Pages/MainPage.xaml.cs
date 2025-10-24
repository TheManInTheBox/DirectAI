using MusicPlatform.Maui.ViewModels;
using CommunityToolkit.Maui.Views;

namespace MusicPlatform.Maui.Pages;

public partial class MainPage : ContentPage
{
    private readonly MainViewModel _viewModel;

    public MainPage(MainViewModel viewModel)
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
    
    private void OnMediaElementLoaded(object? sender, EventArgs e)
    {
        if (sender is MediaElement mediaElement && 
            mediaElement.BindingContext is GeneratedMusicItem item)
        {
            item.AudioPlayer = mediaElement;
        }
    }

    private void OnDragOver(object? sender, DragEventArgs e)
    {
        try
        {
#if WINDOWS
            // Windows-specific drag over handling
            if (e.PlatformArgs?.DragEventArgs is Microsoft.UI.Xaml.DragEventArgs winArgs)
            {
                // Check if dragged data contains storage items (files)
                if (winArgs.DataView.Contains(Windows.ApplicationModel.DataTransfer.StandardDataFormats.StorageItems))
                {
                    e.AcceptedOperation = DataPackageOperation.Copy;
                    winArgs.AcceptedOperation = Windows.ApplicationModel.DataTransfer.DataPackageOperation.Copy;
                    
                    // Visual feedback - highlight drop zone
                    if (sender is Border border)
                    {
                        border.BackgroundColor = Color.FromArgb("#E3F2FD"); // Light blue highlight
                        border.Stroke = Color.FromArgb("#2196F3"); // Blue border
                    }
                }
                else
                {
                    e.AcceptedOperation = DataPackageOperation.None;
                    winArgs.AcceptedOperation = Windows.ApplicationModel.DataTransfer.DataPackageOperation.None;
                }
            }
#else
            e.AcceptedOperation = DataPackageOperation.None;
#endif
        }
        catch (Exception ex)
        {
            // Silently fail on drag over errors to prevent crashes
            System.Diagnostics.Debug.WriteLine($"Drag over error: {ex.Message}");
            e.AcceptedOperation = DataPackageOperation.None;
        }
    }

    private void OnDragLeave(object? sender, DragEventArgs e)
    {
        try
        {
            // Reset visual feedback
            if (sender is Border border)
            {
                border.BackgroundColor = Application.Current?.Resources.ContainsKey("PrimaryLight") == true
                    ? (Color)Application.Current.Resources["PrimaryLight"]
                    : Colors.LightGray;
                border.Stroke = Application.Current?.Resources.ContainsKey("Primary") == true
                    ? (Color)Application.Current.Resources["Primary"]
                    : Colors.Gray;
            }
        }
        catch (Exception ex)
        {
            // Silently fail on drag leave errors to prevent crashes
            System.Diagnostics.Debug.WriteLine($"Drag leave error: {ex.Message}");
        }
    }

    private async void OnDrop(object? sender, DropEventArgs e)
    {
        // Reset visual feedback
        if (sender is Border border)
        {
            border.BackgroundColor = Application.Current?.Resources.ContainsKey("PrimaryLight") == true
                ? (Color)Application.Current.Resources["PrimaryLight"]
                : Colors.LightGray;
            border.Stroke = Application.Current?.Resources.ContainsKey("Primary") == true
                ? (Color)Application.Current.Resources["Primary"]
                : Colors.Gray;
        }

        try
        {
#if WINDOWS
            // Windows-specific file drop handling
            if (e.PlatformArgs?.DragEventArgs is Microsoft.UI.Xaml.DragEventArgs winArgs)
            {
                if (winArgs.DataView.Contains(Windows.ApplicationModel.DataTransfer.StandardDataFormats.StorageItems))
                {
                    var items = await winArgs.DataView.GetStorageItemsAsync();
                    var filePaths = new List<string>();

                    foreach (var item in items)
                    {
                        if (item is Windows.Storage.StorageFile file)
                        {
                            if (file.FileType.Equals(".mp3", StringComparison.OrdinalIgnoreCase))
                            {
                                filePaths.Add(file.Path);
                            }
                        }
                    }

                    if (filePaths.Any())
                    {
                        await _viewModel.HandleDroppedFilesAsync(filePaths);
                    }
                    else
                    {
                        await DisplayAlert("Invalid Files", "Please drop MP3 files only.", "OK");
                    }
                }
            }
#else
            await DisplayAlert("Not Supported", "Drag and drop is currently only supported on Windows.", "OK");
#endif
        }
        catch (Exception ex)
        {
            await DisplayAlert("Error", $"Failed to process dropped files: {ex.Message}", "OK");
        }
    }
}