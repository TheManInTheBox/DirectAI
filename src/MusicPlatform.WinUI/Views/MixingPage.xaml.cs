using Microsoft.Extensions.DependencyInjection;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using MusicPlatform.WinUI.ViewModels;
using MusicPlatform.WinUI.Models;
using Windows.ApplicationModel.DataTransfer;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using System.Linq;

namespace MusicPlatform.WinUI.Views;

public sealed partial class MixingPage : Page
{
    public MixingViewModel ViewModel { get; }

    public MixingPage()
    {
        this.InitializeComponent();
        ViewModel = App.Services.GetRequiredService<MixingViewModel>();
        DataContext = ViewModel;

        // Force-capture drag events at the drop zone level, even if children mark them handled
        this.Loaded += (s, e) =>
        {
            try
            {
                // Attach to parent TimelineArea Grid first (HIGHEST PRIORITY)
                var timelineArea = FindName("TimelineArea") as UIElement;
                if (timelineArea is not null)
                {
                    timelineArea.AddHandler(UIElement.DragEnterEvent, new DragEventHandler(TracksArea_DragEnter), true);
                    timelineArea.AddHandler(UIElement.DragOverEvent, new DragEventHandler(TracksArea_DragOver), true);
                    timelineArea.AddHandler(UIElement.DropEvent, new DragEventHandler(TracksArea_Drop), true);
                    System.Diagnostics.Debug.WriteLine("[MixingPage] ✓✓✓ Drag handlers attached to TimelineArea Grid (PARENT) with handledEventsToo=true");
                }
                
                // Attach to ScrollViewer (secondary)
                var sv = FindName("TimelineScrollViewer") as UIElement;
                if (sv is not null)
                {
                    sv.AddHandler(UIElement.DragEnterEvent, new DragEventHandler(TracksArea_DragEnter), true);
                    sv.AddHandler(UIElement.DragOverEvent, new DragEventHandler(TracksArea_DragOver), true);
                    sv.AddHandler(UIElement.DropEvent, new DragEventHandler(TracksArea_Drop), true);
                    System.Diagnostics.Debug.WriteLine("[MixingPage] ✓ Drag handlers attached to ScrollViewer with handledEventsToo=true");
                }
                
                // Also attach to Border (backup)
                var dz = FindName("TimelineDropZone") as UIElement;
                if (dz is not null)
                {
                    dz.AddHandler(UIElement.DragEnterEvent, new DragEventHandler(TracksArea_DragEnter), true);
                    dz.AddHandler(UIElement.DragOverEvent, new DragEventHandler(TracksArea_DragOver), true);
                    dz.AddHandler(UIElement.DropEvent, new DragEventHandler(TracksArea_Drop), true);
                    System.Diagnostics.Debug.WriteLine("[MixingPage] ✓ Drag handlers attached to TimelineDropZone with handledEventsToo=true");
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[MixingPage] ✗ Failed to AddHandler for drag events: {ex.Message}");
            }
        };
        
        // Subscribe to cursor position changes
        ViewModel.PropertyChanged += (s, e) =>
        {
            if (e.PropertyName == nameof(ViewModel.PlaybackCursorPosition))
            {
                UpdateCursorPosition();
            }
        };
    }
    
    private void UpdateCursorPosition()
    {
        // Calculate pixel position based on percentage
        // Assuming timeline width of 800px (can be made dynamic later)
        var timelineWidth = 800.0;
        var pixelPosition = (ViewModel.PlaybackCursorPosition / 100.0) * timelineWidth;
        
        PlaybackCursor.X1 = pixelPosition;
        PlaybackCursor.X2 = pixelPosition;
    }

    protected override async void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        
        // Ensure UI is updated with loaded data
        System.Diagnostics.Debug.WriteLine($"MixingPage navigated to - Available audio files: {ViewModel.AvailableAudioFiles.Count}");
        
        // If no audio files are loaded, trigger loading
        if (!ViewModel.AvailableAudioFiles.Any())
        {
            System.Diagnostics.Debug.WriteLine("No audio files found - triggering load");
            await ViewModel.LoadAudioFilesCommand.ExecuteAsync(null);
        }
        else
        {
            System.Diagnostics.Debug.WriteLine("Audio files already loaded from startup");
        }
    }

    private void AudioCard_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        System.Diagnostics.Debug.WriteLine("=== POINTER PRESSED ON AUDIO CARD ===");
        System.Diagnostics.Debug.WriteLine($"  - Original Source: {e.OriginalSource?.GetType().Name}");
        System.Diagnostics.Debug.WriteLine($"  - Pointer Device: {e.Pointer.PointerDeviceType}");
        
        var border = sender as FrameworkElement;
        if (border?.DataContext is AudioFileItemViewModel audioFileItem)
        {
            System.Diagnostics.Debug.WriteLine($"✓ Pointer pressed on: {audioFileItem.AudioFile.OriginalFileName}");
            System.Diagnostics.Debug.WriteLine($"  - Border CanDrag: {(sender as Border)?.CanDrag}");
        }
        else
        {
            System.Diagnostics.Debug.WriteLine($"✗ Could not get AudioFileItemViewModel from DataContext.");
            System.Diagnostics.Debug.WriteLine($"  - Sender: {sender?.GetType().Name}");
            System.Diagnostics.Debug.WriteLine($"  - DataContext: {border?.DataContext?.GetType().Name}");
        }
    }

    private void AudioCard_DragStarting(UIElement sender, DragStartingEventArgs args)
    {
        System.Diagnostics.Debug.WriteLine("=== DRAG STARTING EVENT FIRED ===");
        try
        {
            var border = sender as FrameworkElement;
            System.Diagnostics.Debug.WriteLine($"  - Sender Type: {sender?.GetType().Name}");
            System.Diagnostics.Debug.WriteLine($"  - DataContext Type: {border?.DataContext?.GetType().Name}");
            
            if (border?.DataContext is AudioFileItemViewModel audioFileItem)
            {
                // Set drag data
                args.Data.SetText(audioFileItem.AudioFile.Id.ToString());
                args.Data.RequestedOperation = DataPackageOperation.Copy;
                args.AllowedOperations = DataPackageOperation.Copy;
                
                System.Diagnostics.Debug.WriteLine($"[DRAG] ✓✓✓ Started dragging: {audioFileItem.AudioFile.OriginalFileName}");
                System.Diagnostics.Debug.WriteLine($"[DRAG] Data set as text: {audioFileItem.AudioFile.Id}");
            }
            else
            {
                System.Diagnostics.Debug.WriteLine("[DRAG] ✗ CANCELING - DataContext not AudioFileItemViewModel");
                args.Cancel = true;
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[DRAG] ✗✗✗ ERROR in DragStarting: {ex.Message}");
            System.Diagnostics.Debug.WriteLine($"[DRAG] Stack: {ex.StackTrace}");
            args.Cancel = true;
        }
    }

    private void TracksArea_DragEnter(object sender, DragEventArgs e)
    {
        System.Diagnostics.Debug.WriteLine("=== DRAG ENTER EVENT FIRED ===");
        System.Diagnostics.Debug.WriteLine($"  - Sender Type: {sender?.GetType().Name}");
        System.Diagnostics.Debug.WriteLine($"  - Data Available: {e.DataView.AvailableFormats.Count()} formats");
        
        try
        {
            e.AcceptedOperation = DataPackageOperation.Copy;
            System.Diagnostics.Debug.WriteLine($"  - AcceptedOperation set to: {e.AcceptedOperation}");
            
            // Show big visual drop overlay
            if (FindName("TimelineDropZone") is Border dz)
            {
                dz.Background = new SolidColorBrush(Windows.UI.Color.FromArgb(40, 128, 0, 128)); // Semi-transparent purple
                dz.BorderBrush = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 128, 0, 128));
                dz.BorderThickness = new Thickness(4);
                System.Diagnostics.Debug.WriteLine("  - ✓ Visual highlight applied");
            }
            
            e.Handled = true;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[DRAG] ✗ Error in DragEnter: {ex.Message}");
        }
    }

    private void TracksArea_DragOver(object sender, DragEventArgs e)
    {
        System.Diagnostics.Debug.WriteLine($"[DRAG OVER] Sender: {sender?.GetType().Name}");
        try
        {
            // Must set AcceptedOperation on EVERY DragOver event
            e.AcceptedOperation = DataPackageOperation.Copy;
            e.Handled = true;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[DRAG] ✗ Error in DragOver: {ex.Message}");
        }
    }

    private void TracksArea_DragLeave(object sender, DragEventArgs e)
    {
        try
        {
            System.Diagnostics.Debug.WriteLine("[DRAG] DragLeave fired");
            // Revert visual highlight
            if (FindName("TimelineDropZone") is Border dz)
            {
                dz.BorderThickness = new Thickness(0);
            }
            e.Handled = true;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[DRAG] ✗ Error in DragLeave: {ex.Message}");
        }
    }

    private async void TracksArea_Drop(object sender, DragEventArgs e)
    {
        try
        {
            System.Diagnostics.Debug.WriteLine("[DRAG] ✓ Drop event fired!");
            
            // Revert highlight on successful drop
            if (FindName("TimelineDropZone") is Border dz)
            {
                dz.BorderThickness = new Thickness(0);
            }

            if (e.DataView.Contains(StandardDataFormats.Text))
            {
                var text = await e.DataView.GetTextAsync();
                System.Diagnostics.Debug.WriteLine($"[DRAG] Drop received text: {text}");
                
                if (Guid.TryParse(text, out var audioId))
                {
                    var item = ViewModel.AvailableAudioFiles.FirstOrDefault(a => a.AudioFile.Id == audioId);
                    if (item != null)
                    {
                        System.Diagnostics.Debug.WriteLine($"[DRAG] ✓ Adding audio to mix: {item.AudioFile.OriginalFileName}");
                        await ViewModel.AddAudioToMixAsync(item.AudioFile);
                        e.AcceptedOperation = DataPackageOperation.Copy;
                        e.Handled = true;
                        return;
                    }
                    else
                    {
                        System.Diagnostics.Debug.WriteLine($"[DRAG] ✗ No matching audio file found for ID {audioId}");
                    }
                }
                else
                {
                    System.Diagnostics.Debug.WriteLine("[DRAG] ✗ Dropped text was not a valid GUID");
                }
            }

            System.Diagnostics.Debug.WriteLine("[DRAG] ✗ Drop failed - no valid data");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[DRAG] ✗ Exception in Drop: {ex.Message}");
        }
    }
}
