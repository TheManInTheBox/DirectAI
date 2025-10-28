using Microsoft.Graphics.Canvas;
using Microsoft.Graphics.Canvas.UI.Xaml;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Input;
using System;
using System.Numerics;
using Windows.Foundation;
using Windows.UI;

namespace MusicPlatform.WinUI.Controls;

public sealed partial class AudioTrackControl : UserControl
{
    #region Dependency Properties

    public static readonly DependencyProperty TrackIdProperty =
        DependencyProperty.Register(nameof(TrackId), typeof(Guid), typeof(AudioTrackControl), new PropertyMetadata(Guid.Empty));

    public static readonly DependencyProperty TrackNameProperty =
        DependencyProperty.Register(nameof(TrackName), typeof(string), typeof(AudioTrackControl), 
            new PropertyMetadata("Untitled Track", OnTrackNameChanged));

    public static readonly DependencyProperty WaveformDataProperty =
        DependencyProperty.Register(nameof(WaveformData), typeof(float[]), typeof(AudioTrackControl), 
            new PropertyMetadata(null, OnWaveformDataChanged));

    public static readonly DependencyProperty VolumeProperty =
        DependencyProperty.Register(nameof(Volume), typeof(double), typeof(AudioTrackControl), 
            new PropertyMetadata(0.75));

    public static readonly DependencyProperty PanProperty =
        DependencyProperty.Register(nameof(Pan), typeof(double), typeof(AudioTrackControl), 
            new PropertyMetadata(0.0));

    public static readonly DependencyProperty IsMutedProperty =
        DependencyProperty.Register(nameof(IsMuted), typeof(bool), typeof(AudioTrackControl), 
            new PropertyMetadata(false));

    public static readonly DependencyProperty IsSoloProperty =
        DependencyProperty.Register(nameof(IsSolo), typeof(bool), typeof(AudioTrackControl), 
            new PropertyMetadata(false));

    public static readonly DependencyProperty DurationProperty =
        DependencyProperty.Register(nameof(Duration), typeof(TimeSpan), typeof(AudioTrackControl), 
            new PropertyMetadata(TimeSpan.Zero));

    public static readonly DependencyProperty PlaybackPositionProperty =
        DependencyProperty.Register(nameof(PlaybackPosition), typeof(TimeSpan), typeof(AudioTrackControl), 
            new PropertyMetadata(TimeSpan.Zero, OnPlaybackPositionChanged));

    #endregion

    #region Properties

    public Guid TrackId
    {
        get => (Guid)GetValue(TrackIdProperty);
        set => SetValue(TrackIdProperty, value);
    }

    public string TrackName
    {
        get => (string)GetValue(TrackNameProperty);
        set => SetValue(TrackNameProperty, value);
    }

    public float[] WaveformData
    {
        get => (float[])GetValue(WaveformDataProperty);
        set => SetValue(WaveformDataProperty, value);
    }

    public double Volume
    {
        get => (double)GetValue(VolumeProperty);
        set => SetValue(VolumeProperty, value);
    }

    public double Pan
    {
        get => (double)GetValue(PanProperty);
        set => SetValue(PanProperty, value);
    }

    public bool IsMuted
    {
        get => (bool)GetValue(IsMutedProperty);
        set => SetValue(IsMutedProperty, value);
    }

    public bool IsSolo
    {
        get => (bool)GetValue(IsSoloProperty);
        set => SetValue(IsSoloProperty, value);
    }

    public TimeSpan Duration
    {
        get => (TimeSpan)GetValue(DurationProperty);
        set => SetValue(DurationProperty, value);
    }

    public TimeSpan PlaybackPosition
    {
        get => (TimeSpan)GetValue(PlaybackPositionProperty);
        set => SetValue(PlaybackPositionProperty, value);
    }

    #endregion

    #region Events

    public event EventHandler<SelectionChangedEventArgs>? SelectionChanged;
    public event EventHandler<double>? VolumeChanged;
    public event EventHandler<double>? PanChanged;
    public event EventHandler<bool>? MuteToggled;
    public event EventHandler<bool>? SoloToggled;
    public event EventHandler<ContextMenuRequestedEventArgs>? ContextMenuRequested;

    #endregion

    #region Private Fields

    private WaveformSelection? _currentSelection;
    private SelectionHandle _activeHandle = SelectionHandle.None;
    private Point _dragStartPoint;
    private bool _isDragging = false;
    private TimeSpan _selectionStart = TimeSpan.Zero;
    private TimeSpan _selectionEnd = TimeSpan.Zero;

    // Visual constants
    private readonly Color _waveformColor = Color.FromArgb(255, 74, 144, 226); // Blue
    private readonly Color _selectionColor = Color.FromArgb(128, 255, 165, 0); // Semi-transparent orange
    private readonly Color _handleColor = Color.FromArgb(255, 255, 255, 255); // White
    private readonly Color _playbackCursorColor = Color.FromArgb(255, 255, 107, 107); // Red
    private readonly float _handleRadius = 6f;

    #endregion

    public AudioTrackControl()
    {
        this.InitializeComponent();
        TrackNameText.Text = TrackName;
        VolumeSlider.Value = Volume * 100;
        PanSlider.Value = Pan * 100;
        MuteButton.IsChecked = IsMuted;
        SoloButton.IsChecked = IsSolo;
    }

    #region Property Changed Handlers

    private static void OnTrackNameChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is AudioTrackControl control)
        {
            control.TrackNameText.Text = e.NewValue as string ?? "Untitled Track";
        }
    }

    private static void OnWaveformDataChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is AudioTrackControl control)
        {
            control.WaveformCanvas.Invalidate();
        }
    }

    private static void OnPlaybackPositionChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is AudioTrackControl control)
        {
            control.WaveformCanvas.Invalidate();
        }
    }

    #endregion

    #region Waveform Drawing

    private void WaveformCanvas_Draw(CanvasControl sender, CanvasDrawEventArgs args)
    {
        var session = args.DrawingSession;
        var size = sender.Size;

        // Clear background
        session.Clear(Color.FromArgb(255, 45, 45, 48));

        if (WaveformData == null || WaveformData.Length == 0)
        {
            DrawEmptyState(session, size);
            return;
        }

        // Draw waveform
        DrawWaveform(session, size);

        // Draw selection overlay
        if (_currentSelection != null && _currentSelection.IsActive)
        {
            DrawSelection(session, size);
        }

        // Draw playback cursor
        if (PlaybackPosition > TimeSpan.Zero && Duration > TimeSpan.Zero)
        {
            DrawPlaybackCursor(session, size);
        }
    }

    private void DrawEmptyState(CanvasDrawingSession session, Size size)
    {
        var text = "No waveform data";
        var textFormat = new Microsoft.Graphics.Canvas.Text.CanvasTextFormat
        {
            FontSize = 14,
            HorizontalAlignment = Microsoft.Graphics.Canvas.Text.CanvasHorizontalAlignment.Center,
            VerticalAlignment = Microsoft.Graphics.Canvas.Text.CanvasVerticalAlignment.Center
        };

        session.DrawText(
            text,
            new Vector2((float)(size.Width / 2), (float)(size.Height / 2)),
            Colors.Gray,
            textFormat);
    }

    private void DrawWaveform(CanvasDrawingSession session, Size size)
    {
        if (WaveformData == null || WaveformData.Length < 2) return;

        float centerY = (float)(size.Height / 2);
        float amplitude = (float)(size.Height * 0.4); // 40% of height for wave amplitude
        float stepX = (float)size.Width / WaveformData.Length;

        // Draw waveform as lines
        for (int i = 0; i < WaveformData.Length - 1; i++)
        {
            float x1 = i * stepX;
            float x2 = (i + 1) * stepX;
            float y1 = centerY - (WaveformData[i] * amplitude);
            float y2 = centerY - (WaveformData[i + 1] * amplitude);

            session.DrawLine(
                new Vector2(x1, y1),
                new Vector2(x2, y2),
                _waveformColor,
                1.5f);
        }

        // Draw center line
        session.DrawLine(
            new Vector2(0, centerY),
            new Vector2((float)size.Width, centerY),
            Color.FromArgb(40, 255, 255, 255),
            1f);
    }

    private void DrawSelection(CanvasDrawingSession session, Size size)
    {
        if (_currentSelection == null) return;

        var rect = GetSelectionRect(size);

        // Draw selection overlay
        session.FillRectangle(rect, _selectionColor);

        // Draw selection border
        session.DrawRectangle(rect, _handleColor, 2f);

        // Draw resize handles
        DrawHandle(session, new Vector2((float)rect.X, (float)(rect.Y + rect.Height / 2))); // Left
        DrawHandle(session, new Vector2((float)(rect.X + rect.Width), (float)(rect.Y + rect.Height / 2))); // Right
    }

    private void DrawHandle(CanvasDrawingSession session, Vector2 position)
    {
        session.FillCircle(position, _handleRadius, _handleColor);
        session.DrawCircle(position, _handleRadius, Colors.Black, 1f);
    }

    private void DrawPlaybackCursor(CanvasDrawingSession session, Size size)
    {
        if (Duration.TotalSeconds == 0) return;

        float position = (float)((PlaybackPosition.TotalSeconds / Duration.TotalSeconds) * size.Width);

        session.DrawLine(
            new Vector2(position, 0),
            new Vector2(position, (float)size.Height),
            _playbackCursorColor,
            2f);
    }

    #endregion

    #region Mouse/Pointer Interaction

    private void WaveformCanvas_PointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(WaveformCanvas).Position;
        _dragStartPoint = point;
        _isDragging = true;

        // Check if clicking on handle
        var size = WaveformCanvas.Size;
        var rect = GetSelectionRect(size);

        if (_currentSelection != null && _currentSelection.IsActive)
        {
            var leftHandle = new Point(rect.X, rect.Y + rect.Height / 2);
            var rightHandle = new Point(rect.X + rect.Width, rect.Y + rect.Height / 2);

            if (IsPointNearHandle(point, leftHandle))
            {
                _activeHandle = SelectionHandle.Left;
                WaveformCanvas.CapturePointer(e.Pointer);
                return;
            }
            else if (IsPointNearHandle(point, rightHandle))
            {
                _activeHandle = SelectionHandle.Right;
                WaveformCanvas.CapturePointer(e.Pointer);
                return;
            }
            else if (rect.Contains(point))
            {
                _activeHandle = SelectionHandle.Body;
                WaveformCanvas.CapturePointer(e.Pointer);
                return;
            }
        }

        // Start new selection
        _activeHandle = SelectionHandle.Creating;
        _selectionStart = PixelToTime(point.X, size.Width);
        _selectionEnd = _selectionStart;
        
        _currentSelection = new WaveformSelection
        {
            StartTime = _selectionStart,
            EndTime = _selectionEnd,
            IsActive = true
        };

        WaveformCanvas.CapturePointer(e.Pointer);
        WaveformCanvas.Invalidate();
    }

    private void WaveformCanvas_PointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!_isDragging || _currentSelection == null) return;

        var point = e.GetCurrentPoint(WaveformCanvas).Position;
        var size = WaveformCanvas.Size;
        var time = PixelToTime(point.X, size.Width);

        switch (_activeHandle)
        {
            case SelectionHandle.Creating:
                _selectionEnd = time;
                _currentSelection = _currentSelection with
                {
                    StartTime = TimeSpan.FromSeconds(Math.Min(_selectionStart.TotalSeconds, time.TotalSeconds)),
                    EndTime = TimeSpan.FromSeconds(Math.Max(_selectionStart.TotalSeconds, time.TotalSeconds))
                };
                break;

            case SelectionHandle.Left:
                _currentSelection = _currentSelection with
                {
                    StartTime = TimeSpan.FromSeconds(Math.Min(time.TotalSeconds, _currentSelection.EndTime.TotalSeconds - 0.1))
                };
                break;

            case SelectionHandle.Right:
                _currentSelection = _currentSelection with
                {
                    EndTime = TimeSpan.FromSeconds(Math.Max(time.TotalSeconds, _currentSelection.StartTime.TotalSeconds + 0.1))
                };
                break;

            case SelectionHandle.Body:
                var delta = PixelToTime(point.X - _dragStartPoint.X, size.Width);
                var duration = _currentSelection.EndTime - _currentSelection.StartTime;
                var newStart = _currentSelection.StartTime + delta;
                if (newStart >= TimeSpan.Zero && newStart + duration <= Duration)
                {
                    _currentSelection = _currentSelection with
                    {
                        StartTime = newStart,
                        EndTime = newStart + duration
                    };
                    _dragStartPoint = point;
                }
                break;
        }

        WaveformCanvas.Invalidate();
    }

    private void WaveformCanvas_PointerReleased(object sender, PointerRoutedEventArgs e)
    {
        if (_isDragging && _currentSelection != null)
        {
            SelectionChanged?.Invoke(this, new SelectionChangedEventArgs(
                _currentSelection.StartTime,
                _currentSelection.EndTime));
        }

        _isDragging = false;
        _activeHandle = SelectionHandle.None;
        WaveformCanvas.ReleasePointerCapture(e.Pointer);
    }

    private void WaveformCanvas_RightTapped(object sender, RightTappedRoutedEventArgs e)
    {
        if (_currentSelection != null && _currentSelection.IsActive)
        {
            SelectionContextMenu.ShowAt(WaveformCanvas, e.GetPosition(WaveformCanvas));
        }
    }

    #endregion

    #region Helper Methods

    private Rect GetSelectionRect(Size canvasSize)
    {
        if (_currentSelection == null || Duration.TotalSeconds == 0)
            return Rect.Empty;

        double startX = (_currentSelection.StartTime.TotalSeconds / Duration.TotalSeconds) * canvasSize.Width;
        double endX = (_currentSelection.EndTime.TotalSeconds / Duration.TotalSeconds) * canvasSize.Width;
        double width = endX - startX;

        return new Rect(startX, 0, width, canvasSize.Height - 20); // -20 for timeline
    }

    private TimeSpan PixelToTime(double pixelX, double canvasWidth)
    {
        if (Duration.TotalSeconds == 0) return TimeSpan.Zero;
        double ratio = Math.Max(0, Math.Min(1, pixelX / canvasWidth));
        return TimeSpan.FromSeconds(ratio * Duration.TotalSeconds);
    }

    private bool IsPointNearHandle(Point point, Point handle, double threshold = 15)
    {
        double distance = Math.Sqrt(
            Math.Pow(point.X - handle.X, 2) + 
            Math.Pow(point.Y - handle.Y, 2));
        return distance <= threshold;
    }

    public void ClearSelection()
    {
        _currentSelection = null;
        WaveformCanvas.Invalidate();
    }

    #endregion

    #region Control Event Handlers

    private void VolumeSlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        Volume = e.NewValue / 100.0;
        VolumeText.Text = $"{(int)e.NewValue}%";
        VolumeChanged?.Invoke(this, Volume);
    }

    private void PanSlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        Pan = e.NewValue / 100.0;
        
        // Update pan text
        var pan = (int)e.NewValue;
        if (Math.Abs(pan) < 1)
            PanText.Text = "C";
        else
            PanText.Text = pan < 0 ? $"L{Math.Abs(pan)}" : $"R{pan}";
            
        PanChanged?.Invoke(this, Pan);
    }

    private void MuteButton_Click(object sender, RoutedEventArgs e)
    {
        IsMuted = MuteButton.IsChecked ?? false;
        MuteToggled?.Invoke(this, IsMuted);
    }

    private void SoloButton_Click(object sender, RoutedEventArgs e)
    {
        IsSolo = SoloButton.IsChecked ?? false;
        SoloToggled?.Invoke(this, IsSolo);
    }

    #endregion

    #region Context Menu Handlers

    private void ContextMenu_Cut(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.Cut, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    private void ContextMenu_Copy(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.Copy, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    private void ContextMenu_Paste(object sender, RoutedEventArgs e)
    {
        ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
            ContextMenuAction.Paste, PlaybackPosition, PlaybackPosition));
    }

    private void ContextMenu_Delete(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.Delete, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    private void ContextMenu_AIGenerate(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.AIGenerate, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    private void ContextMenu_Loop(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.Loop, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    private void ContextMenu_Normalize(object sender, RoutedEventArgs e)
    {
        if (_currentSelection != null)
        {
            ContextMenuRequested?.Invoke(this, new ContextMenuRequestedEventArgs(
                ContextMenuAction.Normalize, _currentSelection.StartTime, _currentSelection.EndTime));
        }
    }

    #endregion
}

#region Supporting Classes

public record WaveformSelection
{
    public TimeSpan StartTime { get; init; }
    public TimeSpan EndTime { get; init; }
    public bool IsActive { get; init; }
}

public enum SelectionHandle
{
    None,
    Creating,
    Left,
    Right,
    Body
}

public enum ContextMenuAction
{
    Cut,
    Copy,
    Paste,
    Delete,
    AIGenerate,
    Loop,
    Normalize
}

public class SelectionChangedEventArgs : EventArgs
{
    public TimeSpan StartTime { get; }
    public TimeSpan EndTime { get; }

    public SelectionChangedEventArgs(TimeSpan startTime, TimeSpan endTime)
    {
        StartTime = startTime;
        EndTime = endTime;
    }
}

public class ContextMenuRequestedEventArgs : EventArgs
{
    public ContextMenuAction Action { get; }
    public TimeSpan StartTime { get; }
    public TimeSpan EndTime { get; }

    public ContextMenuRequestedEventArgs(ContextMenuAction action, TimeSpan startTime, TimeSpan endTime)
    {
        Action = action;
        StartTime = startTime;
        EndTime = endTime;
    }
}

#endregion
