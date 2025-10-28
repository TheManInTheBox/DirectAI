using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Markup;
using System;
using System.Diagnostics;

namespace MusicPlatform.WinUI.Controls;

public sealed partial class WaveformControl : UserControl
{
    private bool _isSelecting = false;
    private double _selectionStartX = 0;
    private double _selectionEndX = 0;

    public WaveformControl()
    {
        this.InitializeComponent();
        this.SizeChanged += OnSizeChanged;
    }

    #region Dependency Properties

    public static readonly DependencyProperty WaveformDataProperty =
        DependencyProperty.Register(
            nameof(WaveformData),
            typeof(string),
            typeof(WaveformControl),
            new PropertyMetadata(null, OnWaveformDataChanged));

    public string WaveformData
    {
        get => (string)GetValue(WaveformDataProperty);
        set => SetValue(WaveformDataProperty, value);
    }

    public static readonly DependencyProperty SelectionStartProperty =
        DependencyProperty.Register(
            nameof(SelectionStart),
            typeof(double),
            typeof(WaveformControl),
            new PropertyMetadata(0.0, OnSelectionChanged));

    public double SelectionStart
    {
        get => (double)GetValue(SelectionStartProperty);
        set => SetValue(SelectionStartProperty, value);
    }

    public static readonly DependencyProperty SelectionEndProperty =
        DependencyProperty.Register(
            nameof(SelectionEnd),
            typeof(double),
            typeof(WaveformControl),
            new PropertyMetadata(1.0, OnSelectionChanged));

    public double SelectionEnd
    {
        get => (double)GetValue(SelectionEndProperty);
        set => SetValue(SelectionEndProperty, value);
    }

    #endregion

    private static void OnWaveformDataChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is WaveformControl control)
        {
            var pathData = e.NewValue as string;
            Debug.WriteLine($"[WaveformControl] OnWaveformDataChanged called");
            Debug.WriteLine($"[WaveformControl] PathData is null: {pathData == null}");
            Debug.WriteLine($"[WaveformControl] PathData is empty: {string.IsNullOrEmpty(pathData)}");
            
            if (pathData != null)
            {
                var preview = pathData.Length > 100 ? pathData.Substring(0, 100) + "..." : pathData;
                Debug.WriteLine($"[WaveformControl] PathData preview: {preview}");
                Debug.WriteLine($"[WaveformControl] PathData length: {pathData.Length}");
            }
            
            if (!string.IsNullOrEmpty(pathData))
            {
                try
                {
                    var geometry = (Geometry)XamlReader.Load($"<PathGeometry xmlns='http://schemas.microsoft.com/winfx/2006/xaml/presentation'>{pathData}</PathGeometry>");
                    control.WaveformPath.Data = geometry;
                    Debug.WriteLine($"[WaveformControl] Successfully set geometry: {geometry}");
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[WaveformControl] Error setting waveform data: {ex.Message}");
                    Debug.WriteLine($"[WaveformControl] Stack trace: {ex.StackTrace}");
                }
            }
            else
            {
                Debug.WriteLine($"[WaveformControl] Skipping geometry update - pathData is null or empty");
            }
        }
    }

    private static void OnSelectionChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is WaveformControl control)
        {
            control.UpdateSelectionDisplay();
        }
    }

    private void OnSizeChanged(object sender, SizeChangedEventArgs e)
    {
        UpdateSelectionDisplay();
    }

    private void OnPointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        if (point.Properties.IsLeftButtonPressed)
        {
            _isSelecting = true;
            _selectionStartX = point.Position.X;
            _selectionEndX = point.Position.X;
            
            this.CapturePointer(e.Pointer);
            UpdateSelectionVisual();
            
            Debug.WriteLine($"[WaveformControl] Selection started at {_selectionStartX}px");
        }
    }

    private void OnPointerMoved(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        
        // Update hover line
        if (!_isSelecting)
        {
            HoverLine.Visibility = Visibility.Visible;
            Canvas.SetLeft(HoverLine, point.Position.X);
        }
        
        // Update selection
        if (_isSelecting)
        {
            _selectionEndX = Math.Clamp(point.Position.X, 0, this.ActualWidth);
            UpdateSelectionVisual();
        }
    }

    private void OnPointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (_isSelecting)
        {
            _isSelecting = false;
            this.ReleasePointerCapture(e.Pointer);
            
            // Convert pixel positions to normalized values (0.0 to 1.0)
            double width = this.ActualWidth;
            if (width > 0)
            {
                double start = Math.Min(_selectionStartX, _selectionEndX) / width;
                double end = Math.Max(_selectionStartX, _selectionEndX) / width;
                
                SelectionStart = Math.Clamp(start, 0, 1);
                SelectionEnd = Math.Clamp(end, 0, 1);
                
                Debug.WriteLine($"[WaveformControl] Selection: {SelectionStart:F3} to {SelectionEnd:F3} ({(SelectionEnd - SelectionStart) * 100:F1}%)");
                
                // Raise event for selection changed
                SelectionChanged?.Invoke(this, EventArgs.Empty);
            }
        }
    }

    private void UpdateSelectionVisual()
    {
        double left = Math.Min(_selectionStartX, _selectionEndX);
        double right = Math.Max(_selectionStartX, _selectionEndX);
        double width = right - left;
        
        if (width > 2)
        {
            SelectionRect.Visibility = Visibility.Visible;
            SelectionLeftBorder.Visibility = Visibility.Visible;
            SelectionRightBorder.Visibility = Visibility.Visible;
            
            Canvas.SetLeft(SelectionRect, left);
            SelectionRect.Width = width;
            SelectionRect.Height = this.ActualHeight;
            
            Canvas.SetLeft(SelectionLeftBorder, left);
            SelectionLeftBorder.Height = this.ActualHeight;
            
            Canvas.SetLeft(SelectionRightBorder, right - 3);
            SelectionRightBorder.Height = this.ActualHeight;
        }
        else
        {
            SelectionRect.Visibility = Visibility.Collapsed;
            SelectionLeftBorder.Visibility = Visibility.Collapsed;
            SelectionRightBorder.Visibility = Visibility.Collapsed;
        }
    }

    private void UpdateSelectionDisplay()
    {
        double width = this.ActualWidth;
        if (width > 0 && (SelectionEnd - SelectionStart) > 0.001)
        {
            double left = SelectionStart * width;
            double right = SelectionEnd * width;
            double selWidth = right - left;
            
            SelectionRect.Visibility = Visibility.Visible;
            SelectionLeftBorder.Visibility = Visibility.Visible;
            SelectionRightBorder.Visibility = Visibility.Visible;
            
            Canvas.SetLeft(SelectionRect, left);
            SelectionRect.Width = selWidth;
            SelectionRect.Height = this.ActualHeight;
            
            Canvas.SetLeft(SelectionLeftBorder, left);
            SelectionLeftBorder.Height = this.ActualHeight;
            
            Canvas.SetLeft(SelectionRightBorder, right - 3);
            SelectionRightBorder.Height = this.ActualHeight;
        }
        else
        {
            SelectionRect.Visibility = Visibility.Collapsed;
            SelectionLeftBorder.Visibility = Visibility.Collapsed;
            SelectionRightBorder.Visibility = Visibility.Collapsed;
        }
    }

    public event EventHandler? SelectionChanged;
}
