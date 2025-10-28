using Microsoft.UI.Xaml.Data;

namespace MusicPlatform.WinUI.Converters;

public class StemTypeToIconConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var stemType = value as string ?? string.Empty;
        
        return stemType.ToLower() switch
        {
            "vocals" or "vocal" => "\uE720", // 🎤 Microphone
            "drums" or "drum" => "\uE8FD", // 🥁 Drum
            "bass" => "\uE189", // Bass - using audio/sound wave icon
            "guitar" or "other" => "\uEC4F", // Guitar/Other - music note
            _ => "\uE8D6" // Default - generic music
        };
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}
