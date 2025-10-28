using Microsoft.UI.Xaml.Data;
using System;

namespace MusicPlatform.WinUI.Converters;

public class VolumeFormatConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is double volume)
        {
            return $"{(int)volume}%";
        }
        return "0%";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public class PanFormatConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value is double pan)
        {
            if (Math.Abs(pan) < 1)
                return "C"; // Center
            return pan < 0 ? $"L{Math.Abs((int)pan)}" : $"R{(int)pan}";
        }
        return "C";
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}
