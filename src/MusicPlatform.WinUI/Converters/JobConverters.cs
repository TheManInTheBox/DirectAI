using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using MusicPlatform.WinUI.Models;
using Windows.UI;

namespace MusicPlatform.WinUI.Views;

/// <summary>
/// Converts job type to appropriate icon glyph
/// </summary>
public class JobTypeToIconConverter : IValueConverter
{
    public static JobTypeToIconConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is string jobType)
        {
            return jobType.ToLowerInvariant() switch
            {
                "analysis" => "\uE9F9", // Chart icon
                "generation" => "\uE7C3", // Sparkle icon
                "upload" => "\uE898", // Upload icon
                "stemSeparation" => "\uE8B7", // Waveform icon
                _ => "\uE9F3" // Generic process icon
            };
        }
        return "\uE9F3";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Converts job status to status indicator color
/// </summary>
public class JobStatusToColorConverter : IValueConverter
{
    public static JobStatusToColorConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is string status)
        {
            return status.ToLowerInvariant() switch
            {
                "pending" => new SolidColorBrush(Color.FromArgb(255, 255, 193, 7)), // Yellow
                "running" => new SolidColorBrush(Color.FromArgb(255, 0, 123, 255)), // Blue
                "completed" => new SolidColorBrush(Color.FromArgb(255, 40, 167, 69)), // Green
                "failed" => new SolidColorBrush(Color.FromArgb(255, 220, 53, 69)), // Red
                "cancelled" => new SolidColorBrush(Color.FromArgb(255, 108, 117, 125)), // Gray
                _ => new SolidColorBrush(Color.FromArgb(255, 108, 117, 125)) // Default gray
            };
        }
        return new SolidColorBrush(Color.FromArgb(255, 108, 117, 125));
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Calculates job duration from start time
/// </summary>
public class JobDurationConverter : IValueConverter
{
    public static JobDurationConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is JobDto job)
        {
            var endTime = job.CompletedAt ?? DateTime.UtcNow;
            var duration = endTime - job.StartedAt;
            
            if (duration.TotalDays >= 1)
                return $"{duration.Days}d {duration.Hours}h";
            else if (duration.TotalHours >= 1)
                return $"{duration.Hours}h {duration.Minutes}m";
            else if (duration.TotalMinutes >= 1)
                return $"{duration.Minutes}m {duration.Seconds}s";
            else
                return $"{duration.Seconds}s";
        }
        return "0s";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Calculates progress percentage for running jobs
/// </summary>
public class JobProgressConverter : IValueConverter
{
    public static JobProgressConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is JobDto job)
        {
            // For running jobs, calculate progress based on steps or time
            if (job.Status.Equals("Running", StringComparison.OrdinalIgnoreCase))
            {
                // Simple time-based progress estimation
                var elapsed = DateTime.UtcNow - job.StartedAt;
                var estimatedTotal = TimeSpan.FromMinutes(2); // Estimate 2 minutes per job
                var progress = Math.Min(85, (elapsed.TotalSeconds / estimatedTotal.TotalSeconds) * 100);
                return progress;
            }
            else if (job.Status.Equals("Completed", StringComparison.OrdinalIgnoreCase))
            {
                return 100.0;
            }
        }
        return 0.0;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Shows progress bar only for running jobs
/// </summary>
public class RunningJobVisibilityConverter : IValueConverter
{
    public static RunningJobVisibilityConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is string status)
        {
            return status.Equals("Running", StringComparison.OrdinalIgnoreCase) ? 
                Visibility.Visible : Visibility.Collapsed;
        }
        return Visibility.Collapsed;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Shows error details only for failed jobs
/// </summary>
public class FailedJobVisibilityConverter : IValueConverter
{
    public static FailedJobVisibilityConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is string status)
        {
            return status.Equals("Failed", StringComparison.OrdinalIgnoreCase) ? 
                Visibility.Visible : Visibility.Collapsed;
        }
        return Visibility.Collapsed;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Shows empty state when no jobs exist
/// </summary>
public class EmptyJobsVisibilityConverter : IValueConverter
{
    public static EmptyJobsVisibilityConverter Instance { get; } = new();

    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is int count)
        {
            return count == 0 ? Visibility.Visible : Visibility.Collapsed;
        }
        return Visibility.Visible;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}