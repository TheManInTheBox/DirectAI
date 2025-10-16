# Real-Time Job Progress Tracking

## Overview
Implemented real-time progress tracking on the Jobs page with adaptive polling, visual progress indicators, and smooth UI updates.

## Features Implemented

### 1. **Adaptive Polling** ⚡
- **Fast polling when active**: 2 seconds when jobs are Running/Pending
- **Slower polling when idle**: 5 seconds when all jobs are Completed/Failed
- Automatically adjusts refresh rate based on job activity
- Reduces API load when no active work is happening

### 2. **Smart UI Updates** 🎨
- **Incremental updates**: Only updates changed items instead of rebuilding entire list
- **Prevents flickering**: Items update in-place without list rebuild
- **Smooth transitions**: Jobs fade between states instead of popping
- Maintains scroll position during updates

### 3. **Visual Progress Indicators** 📊
- **Progress bar**: Shows completion percentage for running jobs
- **Live indicator**: Green dot (●) appears when jobs are actively running
- **Step-based progress**: Maps job steps to progress percentages:
  - `initializing` → 5%
  - `downloading_audio` → 15%
  - `calling_analysis_worker` → 20%
  - `worker_processing` → 60% (bulk of work)
  - `uploading_results` → 90%
  - `Completed` → 100%

### 4. **Enhanced Status Messages** 💬
- Real-time status updates with emoji indicators
- Shows active job count and refresh interval
- Examples:
  - `🔄 Live: 2 active job(s) • Refreshing every 2s`
  - `✅ 5 job(s) • All idle`

### 5. **Progress Messages** 📝
Context-aware messages that update as job progresses:
- `🚀 Starting analysis...`
- `⬇️ Downloading audio file...`
- `📞 Calling analysis worker...`
- `🔬 Processing audio (separation + analysis)...`
- `⬆️ Uploading results...`
- `✅ Analysis complete`

## Technical Implementation

### JobsViewModel Changes

#### Adaptive Polling
```csharp
private int GetRefreshInterval()
{
    var activeJobs = Jobs.Count(j => j.Status == "Running" || j.Status == "Pending");
    return activeJobs > 0 ? 2 : 5; // 2s when active, 5s when idle
}
```

#### Smart Update Logic
```csharp
// Only rebuild list if count changed significantly (>3 items)
if (Math.Abs(Jobs.Count - jobs.Count()) > 3)
{
    Jobs.Clear();
    // Add all items
}
else
{
    // Update existing items in-place
    // Add new items
    // Remove deleted items
}
```

#### Progress Calculation
```csharp
private static int GetProgressPercentage(string status, string? currentStep)
{
    if (status == "Completed") return 100;
    if (status == "Running" && !string.IsNullOrEmpty(currentStep))
    {
        return currentStep switch
        {
            "initializing" => 5,
            "downloading_audio" => 15,
            "calling_analysis_worker" => 20,
            "worker_processing" => 60,
            "uploading_results" => 90,
            _ => 50
        };
    }
    return 25;
}
```

### JobItem Properties
Added new properties for progress tracking:
- `ProgressPercentage` (int): 0-100 completion percentage
- `ProgressDecimal` (double): 0.0-1.0 for ProgressBar binding
- `ProgressMessage` (string): Human-readable progress description

### XAML Changes

#### Progress Bar Display
```xaml
<Grid IsVisible="{Binding Status, Converter={StaticResource StringEqualsConverter}, ConverterParameter=Running}">
    <ProgressBar Progress="{Binding ProgressDecimal}"
                 ProgressColor="{StaticResource Primary}"
                 HeightRequest="6"
                 Margin="0,5,0,0"/>
    <Label Text="{Binding ProgressPercentage, StringFormat='{0}%'}"
           FontSize="10"
           TextColor="{StaticResource Primary}"
           HorizontalOptions="End"/>
</Grid>
```

#### Live Indicator
```xaml
<HorizontalStackLayout Grid.Row="1" HorizontalOptions="Center" Spacing="5">
    <Label Text="●"
           FontSize="14"
           TextColor="LimeGreen"
           IsVisible="{Binding Statistics.RunningJobs, Converter={StaticResource IsGreaterThanZeroConverter}}"/>
    <Label Text="{Binding StatusMessage}"/>
</HorizontalStackLayout>
```

## Converters Added
- `IsGreaterThanZeroConverter`: Converts integer to boolean (true if > 0)

## Null Safety Improvements
- Initialize `Statistics` with default values in constructor
- Handle null API responses gracefully
- Non-nullable `Statistics` property prevents null reference exceptions

## User Experience

### Before
- Manual refresh only
- No progress indication
- List rebuilds on every refresh (flickering)
- No visibility into job progress
- 10-second refresh interval (too slow)

### After
- ✅ Automatic real-time updates
- ✅ Visual progress bars showing completion %
- ✅ Step-by-step progress messages
- ✅ Live indicator when jobs are active
- ✅ Smooth incremental updates (no flickering)
- ✅ Adaptive polling (2s active, 5s idle)
- ✅ Clear status messages with job counts

## Performance Optimizations
1. **Reduced API calls**: Only 2s polling when needed, 5s when idle
2. **Efficient updates**: Update existing items instead of rebuilding list
3. **Background thread**: Polling runs on background thread, doesn't block UI
4. **Cancellation support**: Properly cancels refresh when ViewModel disposed

## Future Enhancements (Optional)
- SignalR/WebSocket for push notifications (eliminates polling)
- Estimated time remaining based on historical data
- Job queue visualization
- Detailed step-by-step timeline view
- Ability to pause/resume real-time mode

## Testing
To test the real-time progress:
1. Upload an audio file via drag-and-drop
2. Navigate to Jobs page
3. Observe:
   - Green dot (●) appears next to status message
   - Progress bar animates from 5% → 100%
   - Progress messages update in real-time
   - Status changes: Pending → Running → Completed
   - Refresh interval adjusts automatically

## Related Files
- `src/MusicPlatform.Maui/ViewModels/JobsViewModel.cs` - Main implementation
- `src/MusicPlatform.Maui/Pages/JobsPage.xaml` - UI layout
- `src/MusicPlatform.Maui/Converters/ValueConverters.cs` - Added IsGreaterThanZeroConverter
- `src/MusicPlatform.Maui/App.xaml` - Registered new converter
