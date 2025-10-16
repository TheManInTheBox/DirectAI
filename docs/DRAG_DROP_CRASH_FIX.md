# Drag and Drop Crash Fix

## Issue
The UI was crashing when dragging files over the drop zone.

## Root Cause
The `OnDragOver` event handler was trying to access `e.Data.Properties.ContainsKey("Files")`, which doesn't exist in the standard .NET MAUI `DragEventArgs`. This property is not part of the cross-platform MAUI API.

### Original Problematic Code
```csharp
private void OnDragOver(object? sender, DragEventArgs e)
{
    // ❌ This causes crash - e.Data.Properties doesn't exist
    if (e.Data.Properties.ContainsKey("Files"))
    {
        e.AcceptedOperation = DataPackageOperation.Copy;
        // ...
    }
}
```

## Solution
Implemented Windows-specific drag and drop handling using conditional compilation (`#if WINDOWS`) and accessing the platform-specific `PlatformArgs.DragEventArgs`.

### Fixed Code

#### OnDragOver Handler
```csharp
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
                if (sender is Frame frame)
                {
                    frame.BackgroundColor = Color.FromArgb("#E3F2FD");
                    frame.BorderColor = Color.FromArgb("#2196F3");
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
        // Silently fail to prevent crashes
        System.Diagnostics.Debug.WriteLine($"Drag over error: {ex.Message}");
        e.AcceptedOperation = DataPackageOperation.None;
    }
}
```

#### OnDragLeave Handler
Added try-catch for safety:
```csharp
private void OnDragLeave(object? sender, DragEventArgs e)
{
    try
    {
        // Reset visual feedback
        if (sender is Frame frame)
        {
            frame.BackgroundColor = Application.Current?.Resources.ContainsKey("PrimaryLight") == true
                ? (Color)Application.Current.Resources["PrimaryLight"]
                : Colors.LightGray;
            frame.BorderColor = Application.Current?.Resources.ContainsKey("Primary") == true
                ? (Color)Application.Current.Resources["Primary"]
                : Colors.Gray;
        }
    }
    catch (Exception ex)
    {
        // Silently fail to prevent crashes
        System.Diagnostics.Debug.WriteLine($"Drag leave error: {ex.Message}");
    }
}
```

## Key Changes

1. **Platform-Specific API Access**:
   - Use `e.PlatformArgs?.DragEventArgs` to get Windows-specific event args
   - Cast to `Microsoft.UI.Xaml.DragEventArgs` for Windows WinUI3 APIs
   - Access `winArgs.DataView` instead of `e.Data`

2. **Proper Data Format Check**:
   - Use `winArgs.DataView.Contains(StandardDataFormats.StorageItems)` 
   - This correctly checks if files are being dragged

3. **Set Both Operations**:
   - Set both `e.AcceptedOperation` (MAUI) and `winArgs.AcceptedOperation` (Windows)
   - Ensures proper drag behavior on Windows

4. **Error Handling**:
   - Wrapped all handlers in try-catch blocks
   - Silently logs errors to debug output
   - Prevents crashes from unexpected exceptions

5. **Conditional Compilation**:
   - Uses `#if WINDOWS` to ensure Windows-only code compiles correctly
   - Gracefully handles non-Windows platforms

## Testing

### Before Fix
- ❌ UI crashed immediately when dragging file over drop zone
- ❌ Application became unresponsive
- ❌ No visual feedback

### After Fix
- ✅ Drag over works smoothly
- ✅ Drop zone highlights blue when file hovers
- ✅ Drop zone resets when drag leaves
- ✅ Files can be dropped successfully
- ✅ No crashes or errors

## How to Test

1. Build and run the Windows app:
   ```bash
   cd src/MusicPlatform.Maui
   dotnet run -f net9.0-windows10.0.19041.0
   ```

2. Drag an MP3 file from Windows Explorer

3. Hover over the drop zone:
   - ✅ Zone should highlight blue
   - ✅ No crash should occur

4. Drag away from zone:
   - ✅ Zone should return to normal color

5. Drop file on zone:
   - ✅ Upload should begin
   - ✅ Progress indicator appears

## Technical Notes

### Windows WinUI3 API
The fix uses Windows-specific APIs from:
- `Microsoft.UI.Xaml.DragEventArgs` - WinUI3 drag event
- `Windows.ApplicationModel.DataTransfer` - Data transfer APIs
- `Windows.Storage` - File system access

### MAUI Platform Args
MAUI provides `PlatformArgs` property on event args to access platform-specific data:
```csharp
e.PlatformArgs?.DragEventArgs  // Access platform-specific event
```

### Debug Output
All errors are logged to debug output for troubleshooting:
```csharp
System.Diagnostics.Debug.WriteLine($"Drag over error: {ex.Message}");
```

## Related Files
- `src/MusicPlatform.Maui/Pages/MainPage.xaml.cs` - Fixed drag and drop handlers
- `src/MusicPlatform.Maui/Pages/MainPage.xaml` - Drop zone UI (unchanged)

## Prevention
To avoid similar issues in the future:
1. Always use `#if WINDOWS` for Windows-specific APIs
2. Access platform-specific args via `PlatformArgs` property
3. Add try-catch blocks to all event handlers
4. Test drag and drop thoroughly on target platform
5. Check MAUI documentation for platform-specific implementations
