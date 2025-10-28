using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MusicPlatform.WinUI.Views;

public sealed partial class LoadingWindow : Window
{
    public LoadingWindow()
    {
        this.InitializeComponent();
        
        // Set window properties
        this.ExtendsContentIntoTitleBar = true;
        this.SetTitleBar(null);
        
        // Set window size and position
        var appWindow = this.AppWindow;
        appWindow.Resize(new Windows.Graphics.SizeInt32(400, 400));
        
        // Center the window
        var displayArea = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(this.AppWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Nearest);
        if (displayArea != null)
        {
            var x = (displayArea.WorkArea.Width - 400) / 2;
            var y = (displayArea.WorkArea.Height - 400) / 2;
            appWindow.Move(new Windows.Graphics.PointInt32(x, y));
        }
    }

    public void UpdateStatus(string status)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            LoadingStatusText.Text = status;
        });
    }

    public void UpdateStep(int step, bool completed = false)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            var completedBrush = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 0, 128, 0));
            var activeBrush = (SolidColorBrush)Application.Current.Resources["AccentTextFillColorPrimaryBrush"];
            var brush = completed ? completedBrush : activeBrush;

            switch (step)
            {
                case 1:
                    Step1Text.Foreground = brush;
                    if (completed) Step1Text.Text = "✓ Services configured";
                    break;
                case 2:
                    Step2Text.Foreground = brush;
                    if (completed) Step2Text.Text = "✓ API connected";
                    break;
                case 3:
                    Step3Text.Foreground = brush;
                    if (completed) Step3Text.Text = "✓ Audio library loaded";
                    break;
                case 4:
                    Step4Text.Foreground = brush;
                    if (completed) Step4Text.Text = "✓ ViewModels initialized";
                    break;
            }
        });
    }
}