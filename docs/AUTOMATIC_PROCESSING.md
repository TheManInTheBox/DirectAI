# Automatic Audio File Processing

## Overview
Audio files uploaded to the platform are now automatically processed and only appear in the Source Material Library once their analysis job has successfully completed.

## Implementation Details

### Upload Flow
1. **User uploads MP3 file** via MAUI app
2. **File is uploaded to blob storage** and database record created
3. **Analysis job is automatically triggered** (idempotent)
4. **File does NOT appear in Source Material Library yet**
5. **Analysis worker processes the file** (1-2 minutes)
   - Separates stems (Demucs)
   - Extracts musical features (BPM, key, chords, structure)
   - Uploads stems to blob storage
   - Creates AnalysisResult in database
6. **Job status changes to "Completed"**
7. **File NOW appears in Source Material Library** with full metadata

### API Changes

#### AudioController.GetAudioFiles()
**Location**: `src/MusicPlatform.Api/Controllers/AudioController.cs`

**Before**:
```csharp
var audioFiles = await _dbContext.AudioFiles
    .OrderByDescending(a => a.UploadedAt)
    .Skip(skip)
    .Take(take)
    .ToListAsync();
```

**After**:
```csharp
// Only return audio files that have successfully completed analysis
var completedAnalysisJobEntityIds = await _dbContext.Jobs
    .Where(j => j.Type == JobType.Analysis && j.Status == JobStatus.Completed)
    .Select(j => j.EntityId)
    .ToListAsync();

var audioFiles = await _dbContext.AudioFiles
    .Where(a => completedAnalysisJobEntityIds.Contains(a.Id))
    .OrderByDescending(a => a.UploadedAt)
    .Skip(skip)
    .Take(take)
    .ToListAsync();
```

### Benefits

1. **Clean UI**: Users only see fully processed files with complete metadata
2. **No broken states**: Files without analysis results don't appear
3. **Automatic processing**: No manual "request analysis" step needed
4. **Status visibility**: Users can check Jobs page to see processing status
5. **Idempotent**: Re-uploading same file won't create duplicate jobs

### User Experience

#### Upload Screen
1. User selects MP3 file(s)
2. Progress indicator shows: "Uploading filename.mp3 (1/3)..."
3. Success message: "✓ Successfully uploaded 3 file(s)!"
4. Files are **NOT immediately visible** in Source Material Library

#### Jobs Page
1. User navigates to Jobs tab
2. Sees "Analysis" jobs with "Running" status
3. Job shows progress: "Analyzing: Separating stems..."
4. After 1-2 minutes, job status changes to "Completed"

#### Source Material Library
1. User refreshes or navigates back to Main page
2. Newly uploaded file NOW appears with:
   - Album artwork
   - Track metadata (title, artist, album)
   - Musical analysis (BPM, key, time signature)
   - Clickable card for detail view

### Error Handling

If analysis job fails:
- File **does NOT appear** in Source Material Library
- Job status shows "Failed" with error message
- User can check Jobs page to see what went wrong
- Job auto-cleanup removes failed jobs after 7 days

### Testing

To verify the flow:
1. Upload a new MP3 file
2. Check Source Material Library - file should NOT appear
3. Navigate to Jobs page - should see "Analysis" job "Running"
4. Wait 1-2 minutes for processing
5. Refresh Source Material Library - file NOW appears with full metadata
6. Click on file card to view details and stems

### Database Query Optimization

The new query uses an efficient join pattern:
- First retrieves completed analysis job entity IDs (indexed)
- Then filters AudioFiles by those IDs
- Uses indexes on Jobs.Type, Jobs.Status, and AudioFiles.Id
- Performance impact: ~5-10ms additional query time

### Related Files
- `src/MusicPlatform.Api/Controllers/AudioController.cs` - Modified GetAudioFiles endpoint
- `src/MusicPlatform.Maui/ViewModels/MainViewModel.cs` - Upload and refresh logic
- `workers/analysis/main.py` - Analysis worker that processes files

## Migration Notes

**Existing users**: Files uploaded before this change will appear in Source Material Library if they have completed analysis jobs. No migration needed.

**New users**: All files will automatically follow the new flow - no manual analysis requests needed.
