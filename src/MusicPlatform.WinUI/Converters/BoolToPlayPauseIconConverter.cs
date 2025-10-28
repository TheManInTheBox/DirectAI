using Microsoft.UI.Xaml.Data;

namespace MusicPlatform.WinUI.Converters;

public class BoolToPlayPauseIconConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is bool isPlaying)
        {
            // E769 = Pause, E768 = Play
            return isPlaying ? "\uE769" : "\uE768";
        }
        return "\uE768"; // Default to Play icon
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}
