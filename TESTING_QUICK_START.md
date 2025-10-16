# 🚀 Quick Start - E2E Testing
## MVP Final Testing - 30 Minute Guide

---

## Prerequisites ✅
- [ ] Docker Desktop running
- [ ] .NET 9.0 SDK installed
- [ ] 2-3 test MP3 files (3-5 minutes each)

---

## Step 1: Start All Services (5 minutes)

```powershell
# Navigate to project root
cd C:\Users\aaron\OneDrive\Documents\GitHub\DirectAI

# Start Docker services
docker-compose up -d

# Wait 1 minute, then check all services running
docker-compose ps

# Expected: 6 services (db, azurite, api, analysis-worker, generation-worker, pgadmin)
```

---

## Step 2: Initialize Database (2 minutes)

```powershell
# Navigate to API project
cd src\MusicPlatform.Api

# Apply migration (first time only)
dotnet ef database update

# Expected: "Done." message
```

---

## Step 3: Start API (1 minute)

```powershell
# In same terminal (src\MusicPlatform.Api)
dotnet run

# Expected: 
# "Now listening on: http://localhost:5000"
# "Application started"

# Test API: Open browser to http://localhost:5000/swagger
```

---

## Step 4: Start MAUI App (2 minutes)

```powershell
# NEW TERMINAL - Navigate to MAUI project
cd C:\Users\aaron\OneDrive\Documents\GitHub\DirectAI\src\MusicPlatform.Maui

# Run for Windows
dotnet run -f net9.0-windows10.0.19041.0

# Expected: MAUI window opens showing library UI
```

---

## Step 5: Test Upload & Analysis (5 minutes)

### Upload File
1. **Drag MP3** onto upload zone in MAUI app
2. ✅ Watch progress: "Uploading {filename}..."
3. ✅ See card appear in Source Material Library
4. ✅ Status shows file size and "Not Analyzed"

### Analyze File
5. **Click "🔬 Analyze"** button on card
6. ✅ Status changes to "Creating analysis request..."
7. **Wait 30-60 seconds** (Demucs + MIR processing)
8. **Click refresh button** (⟳) on Source Material Library
9. ✅ Card shows "✓ Analyzed" badge
10. ✅ See **BPM, Key, Time Signature** on card
11. ✅ "🎸 Generate Stems" button appears

### Verify Backend
```powershell
# Check database (new terminal)
docker exec -it music-db psql -U postgres -d musicplatform

\dt                           # Show tables
SELECT * FROM "AudioFiles";   # See uploaded file
SELECT * FROM "AnalysisResults";  # See analysis data
\q                            # Exit
```

---

## Step 6: Test Single Generation (5 minutes)

### Generate Stems
1. **Click "🎸 Generate Stems"** on analyzed card
2. ✅ Confirmation dialog appears
3. **Click "OK"** to confirm
4. ✅ Status shows "Creating generation request..."
5. ✅ Status updates to "✓ Generation started!"

### Wait for Processing
6. **Wait 3-5 minutes** (MusicGen AI processing)
7. **Click refresh button** (⟳) on Generated Music Library
8. ✅ See **3 stem cards** appear (guitar, bass, drums)
9. ✅ Each shows duration, file size, timestamp

### Download Stem
10. **Click "⬇ Download"** on any stem card
11. ✅ Status shows "Downloading..."
12. ✅ Status shows "Downloaded successfully!"
13. ✅ File saved to `Documents\MusicPlatform\{filename}`
14. **Play the WAV file** - confirm it's audio

---

## Step 7: Test Multi-Select (5 minutes)

### Upload Multiple Files
1. **Drag 2-3 MP3 files** onto upload zone
2. ✅ All files upload sequentially
3. ✅ All cards appear in Source Material Library

### Batch Analyze (Optional - Skip if short on time)
4. Click "🔬 Analyze" on each card individually
5. Wait 1-3 minutes, refresh
6. ✅ All show "✓ Analyzed"

### Multi-Select Generation
7. **Click ☑ button** (top right of Source Material Library)
8. ✅ Checkboxes appear on analyzed cards
9. ✅ Selection controls bar appears
10. **Click "Select All"**
11. ✅ Counter shows "N selected"
12. **Click "🎸 Generate from Selected"**
13. ✅ Confirmation dialog: "Generate AI stems from N file(s)?"
14. **Click "Generate"**
15. ✅ Status on each card updates
16. ✅ Summary dialog: "Started generation for N file(s)"
17. ✅ Selection mode auto-exits

### Verify Batch Results
18. **Wait 10-15 minutes** (for all stems to complete)
19. **Click refresh** on Generated Music Library
20. ✅ See **9 stems** (3 files × 3 stems each)
21. **Download and play** a few stems

---

## Step 8: Verify Worker Logs (2 minutes)

```powershell
# Analysis Worker
docker logs music-analysis-worker --tail 50

# Expected log entries:
# "Analyzing audio file: {filename}"
# "Running Demucs separation..."
# "Running Essentia analysis..."
# "Analysis complete"

# Generation Worker
docker logs music-generation-worker --tail 50

# Expected log entries:
# "Generating stem: guitar"
# "Loading MusicGen model..."
# "Generation complete"
```

---

## Step 9: Verify Blob Storage (2 minutes)

### Using Azure Storage Explorer
1. **Open Azure Storage Explorer**
2. **Connect to Local Emulator** (Azurite)
3. Navigate to: **Local Emulator > Blob Containers > audio-files**
4. ✅ See uploaded MP3 files
5. ✅ See JAMS annotation files (.jams)
6. ✅ See generated stem files (guitar.wav, bass.wav, drums.wav)

### OR Using Browser
1. Open: http://localhost:10000/devstoreaccount1/audio-files/
2. Browse uploaded files and stems

---

## Step 10: Final Verification (1 minute)

### Checklist
- [ ] ✅ Files upload via drag-and-drop
- [ ] ✅ Analysis completes in 30-60 seconds
- [ ] ✅ Analysis results show BPM, Key, Time Signature
- [ ] ✅ Single stem generation works (3-5 minutes)
- [ ] ✅ Multi-select batch generation works
- [ ] ✅ Stems download successfully
- [ ] ✅ Downloaded WAV files are playable
- [ ] ✅ Database contains correct records
- [ ] ✅ Blob storage contains all files
- [ ] ✅ Worker logs show successful processing
- [ ] ✅ UI remains responsive throughout
- [ ] ✅ No crashes or unhandled exceptions

---

## 🎉 Success!

**If all checkboxes are ✅, your MVP is 100% COMPLETE!**

---

## 🐛 Quick Troubleshooting

### Can't connect to API
```powershell
# Check API is running
curl http://localhost:5000/api/audio/files

# Should return: [] or list of files
```

### Analysis takes too long
- **Normal:** 30-60 seconds per file
- **If longer:** CPU is slow, use shorter test files (< 1 minute)

### Generation fails
```powershell
# Check if model downloaded
docker exec -it music-generation-worker ls -lh /root/.cache/huggingface/hub/

# If empty, manually trigger download (takes ~5 minutes first time)
docker exec -it music-generation-worker python -c "from transformers import MusicgenForConditionalGeneration; MusicgenForConditionalGeneration.from_pretrained('facebook/musicgen-small')"
```

### MAUI app won't start
```powershell
# Rebuild
cd src\MusicPlatform.Maui
dotnet clean
dotnet build -f net9.0-windows10.0.19041.0
dotnet run -f net9.0-windows10.0.19041.0
```

---

## 📊 Expected Timings

| Operation | Time | Notes |
|-----------|------|-------|
| Upload (3min MP3) | 2-5 sec | Depends on file size |
| Analysis | 30-60 sec | CPU only (slower) |
| Single stem generation | 1-3 min | MusicGen AI |
| Batch (3 files) | 10-15 min | 3 files × 3 stems |
| Download stem | 1-2 sec | Local network |

---

## 🎯 Next Action

**After testing passes:**
1. Update todo list: Mark "End-to-End Testing" as ✅ COMPLETE
2. Commit all code to Git
3. Tag release: `v1.0.0-mvp`
4. Deploy to Azure (follow deployment guide)
5. **Celebrate!** 🎉🚀

---

## 📞 Need Help?

- **Full Testing Guide:** `docs/MVP_COMPLETION_GUIDE.md`
- **Architecture:** `docs/MUSIC_PLATFORM_ARCHITECTURE.md`
- **Worker Details:** `docs/ANALYSIS_WORKER_SUMMARY.md`, `docs/GENERATION_WORKER_SUMMARY.md`

---

**⏱️ Total Time: 30 minutes**  
**🎯 Goal: Verify complete end-to-end workflow**  
**✅ Result: Production-ready MVP!**
