# Drag and Drop File Upload

## Overview
The Windows MAUI app now supports drag and drop for MP3 file uploads. Users can drag MP3 files from Windows Explorer directly onto the upload zone.

## Implementation Details

### UI Changes
**Location**: `src/MusicPlatform.Maui/Pages/MainPage.xaml`

Added drag and drop gesture recognizers to the upload Frame:
```xaml
<Frame x:Name="DropZone"
       BorderColor="{StaticResource Primary}"
       CornerRadius="15"
       Padding="40"
       HasShadow="True"
       BackgroundColor="{StaticResource PrimaryLight}">
    <Frame.GestureRecognizers>
        <DropGestureRecognizer AllowDrop="True"
                              Drop="OnDrop"
                              DragOver="OnDragOver"
                              DragLeave="OnDragLeave" />
    </Frame.GestureRecognizers>
    ...
</Frame>
```

### Code-Behind Implementation
**Location**: `src/MusicPlatform.Maui/Pages/MainPage.xaml.cs`

Implemented three event handlers:

1. **OnDragOver**: Validates dropped content and provides visual feedback
   - Checks if dragged data contains files
   - Highlights drop zone with blue border when valid files are detected
   - Rejects non-file drops

2. **OnDragLeave**: Resets visual feedback when drag leaves the zone
   - Restores original colors

3. **OnDrop**: Processes dropped files
   - Windows-specific implementation using `#if WINDOWS` directive
   - Accesses Windows Storage APIs to get file paths
   - Filters for MP3 files only
   - Calls ViewModel to upload files

### ViewModel Integration
**Location**: `src/MusicPlatform.Maui/ViewModels/MainViewModel.cs`

Added public method for drag and drop:
```csharp
/// <summary>
/// Public method for handling dropped files from drag and drop
/// </summary>
public async Task HandleDroppedFilesAsync(IEnumerable<string> filePaths)
{
    await UploadFilesAsync(filePaths);
}
```

This method reuses the existing `UploadFilesAsync` logic, ensuring consistent behavior between:
- File picker selection (button click)
- Drag and drop

## User Experience

### Visual Feedback
1. **Normal State**: Drop zone shows with primary light background and primary border
2. **Drag Over State**: Background changes to light blue (#E3F2FD), border becomes bright blue (#2196F3)
3. **Drag Leave**: Returns to normal state
4. **Drop**: Resets to normal and begins upload

### Upload Flow
1. User drags MP3 file(s) from Windows Explorer
2. Drop zone highlights when hovering over it
3. User releases files onto the drop zone
4. App filters for MP3 files only (shows error if no MP3s)
5. Upload process begins with progress indicator
6. Status message: "Uploading filename.mp3 (1/3)..."
7. Success message: "✓ Successfully uploaded 3 file(s)! Processing analysis..."
8. Info message: "📊 Files are being analyzed. They'll appear in Source Library once processing completes (1-2 min)."

### File Validation
- **Accepted**: `.mp3` files (case-insensitive)
- **Rejected**: All other file types with alert message

## Platform Support

### Windows ✅
Fully supported using Windows.Storage APIs:
- `Windows.ApplicationModel.DataTransfer.StandardDataFormats.StorageItems`
- `Windows.Storage.StorageFile`
- Platform-specific code wrapped in `#if WINDOWS` directive

### Other Platforms ❌
- iOS, Android, macOS: Shows "Not Supported" alert
- Can be implemented later using platform-specific handlers

## Technical Details

### Windows Storage API Usage
```csharp
if (winArgs.DataView.Contains(Windows.ApplicationModel.DataTransfer.StandardDataFormats.StorageItems))
{
    var items = await winArgs.DataView.GetStorageItemsAsync();
    foreach (var item in items)
    {
        if (item is Windows.Storage.StorageFile file)
        {
            if (file.FileType.Equals(".mp3", StringComparison.OrdinalIgnoreCase))
            {
                filePaths.Add(file.Path);
            }
        }
    }
}
```

### Error Handling
- Try-catch around entire drop handler
- Validates file types before processing
- Shows user-friendly alerts for:
  - Invalid file types
  - Processing errors
  - Platform not supported

## Integration with Automatic Processing

Drag and drop works seamlessly with the automatic processing system:

1. **Upload**: Files dropped and uploaded to blob storage
2. **Auto-trigger**: Analysis job automatically created (idempotent)
3. **Processing**: Worker analyzes audio (1-2 minutes)
4. **Completion**: Files appear in Source Material Library once analysis completes successfully

This ensures users can drag-drop multiple files and they'll all be processed automatically without manual intervention.

## Testing Instructions

### Test Drag and Drop
1. Build and run the Windows MAUI app:
   ```bash
   cd src/MusicPlatform.Maui
   dotnet run -f net9.0-windows10.0.19041.0
   ```

2. Open Windows File Explorer and navigate to a folder with MP3 files

3. Test scenarios:
   - **Single file**: Drag one MP3 onto the drop zone
   - **Multiple files**: Drag multiple MP3s at once
   - **Mixed types**: Drag MP3s + other files (should filter to MP3s only)
   - **No MP3s**: Drag non-MP3 files (should show error)
   - **Hover effect**: Drag over zone and see blue highlight
   - **Leave zone**: Drag away and see highlight disappear

4. Verify upload process:
   - Progress indicator appears
   - Status messages show file names
   - Success message appears after upload
   - Analysis processing message shows

5. Check Jobs page:
   - Navigate to Jobs tab
   - Verify Analysis jobs created for each file
   - Watch jobs progress to "Completed"

6. Check Source Material Library:
   - Initially files won't appear
   - After 1-2 minutes, refresh or navigate back
   - Files should now appear with metadata

### Known Limitations

1. **Visual feedback timing**: Highlight changes may have slight delay on slower machines
2. **Large files**: Files over 100MB will be rejected by API (built-in validation)
3. **Network errors**: If API is down, upload will fail with error message
4. **Platform specific**: Only works on Windows build

## Related Files

- `src/MusicPlatform.Maui/Pages/MainPage.xaml` - UI with drop zone
- `src/MusicPlatform.Maui/Pages/MainPage.xaml.cs` - Drag and drop handlers
- `src/MusicPlatform.Maui/ViewModels/MainViewModel.cs` - Upload logic
- `src/MusicPlatform.Api/Controllers/AudioController.cs` - API endpoint with filtering

## Future Enhancements

1. **Multi-platform support**: Implement drag and drop for iOS, Android, macOS
2. **Progress per file**: Show individual progress bars for each file
3. **Cancel support**: Allow canceling uploads in progress
4. **Folder support**: Allow dropping entire folders of MP3s
5. **Drag from app**: Allow dragging files out of the app (export)
6. **Advanced validation**: Check file corruption, sample rate, bit depth before upload
