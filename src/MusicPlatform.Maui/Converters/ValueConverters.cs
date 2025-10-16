using System.Globalization;

namespace MusicPlatform.Maui.Converters;

/// <summary>
/// Converts boolean to inverted boolean
/// </summary>
public class InvertedBoolConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is bool boolValue)
            return !boolValue;
        return false;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is bool boolValue)
            return !boolValue;
        return false;
    }
}

/// <summary>
/// Converts string to boolean (true if not null or empty)
/// </summary>
public class IsNotNullOrEmptyConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        return value is string str && !string.IsNullOrEmpty(str);
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Converts object to boolean (true if not null)
/// </summary>
public class IsNotNullConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        return value != null;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Converts percentage (0-100) to progress value (0-1)
/// </summary>
public class PercentToProgressConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is double percent)
            return percent / 100.0;
        return 0.0;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is double progress)
            return progress * 100.0;
        return 0.0;
    }
}

/// <summary>
/// Converts integer to boolean (true if zero)
/// </summary>
public class IsZeroConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is int intValue)
            return intValue == 0;
        return true;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Converts integer to boolean (true if greater than zero)
/// </summary>
public class IsGreaterThanZeroConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is int intValue)
            return intValue > 0;
        if (value is long longValue)
            return longValue > 0;
        if (value is double doubleValue)
            return doubleValue > 0;
        return false;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}

/// <summary>
/// Converts boolean to color (Primary if true, Secondary if false)
/// Supports parameter in format "TrueColor|FalseColor"
/// </summary>
public class BoolToColorConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is bool boolValue)
        {
            // Check if parameter contains color mapping
            if (parameter is string colorMapping && colorMapping.Contains('|'))
            {
                var colors = colorMapping.Split('|');
                if (colors.Length == 2)
                {
                    var colorName = boolValue ? colors[0] : colors[1];
                    return GetColorByName(colorName);
                }
            }

            if (boolValue)
            {
                // Return Primary color when true
                return Application.Current?.Resources.TryGetValue("Primary", out var primaryColor) == true 
                    ? primaryColor 
                    : Colors.Blue;
            }
        }
        // Return Secondary color when false
        return Application.Current?.Resources.TryGetValue("Secondary", out var secondaryColor) == true 
            ? secondaryColor 
            : Colors.Gray;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }

    private static Color GetColorByName(string colorName)
    {
        // Handle hex colors
        if (colorName.StartsWith("#"))
        {
            return Color.FromArgb(colorName);
        }
        
        return colorName.ToLower() switch
        {
            "red" => Colors.Red,
            "green" => Colors.Green,
            "blue" => Colors.Blue,
            "orange" => Colors.Orange,
            "purple" => Colors.Purple,
            "gray" => Colors.Gray,
            "black" => Colors.Black,
            "white" => Colors.White,
            _ => Colors.Gray
        };
    }
}

/// <summary>
/// Converts string to boolean based on equality with parameter
/// </summary>
public class StringEqualsConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is string stringValue && parameter is string parameterValue)
        {
            return string.Equals(stringValue, parameterValue, StringComparison.OrdinalIgnoreCase);
        }
        return false;
    }

    public object? ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        throw new NotImplementedException();
    }
}
