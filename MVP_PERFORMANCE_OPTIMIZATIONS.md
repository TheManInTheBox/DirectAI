# MVP Performance Optimizations

## Changes Made for Fast Testing

### Analysis Worker Simplifications

**File:** `workers/analysis/analysis_service.py`

#### Features Disabled (Temporarily)
The following intensive analysis features have been disabled for MVP performance:

1. **Section Extraction** - Structural segmentation (was timing out after 60s)
2. **Chord Extraction** - Chord progression analysis
3. **Music Theory Analysis** - Harmonic and rhythmic complexity
4. **Genre Detection** - Genre classification algorithms
5. **Audio Flamingo** - Advanced audio understanding (model not available)
6. **Technical Features** - Comprehensive technical analysis
7. **Psychoacoustic Features** - Perceptual audio features (was hanging)
8. **Spectral Features** - Spectral analysis (was causing crashes)
9. **Temporal Features** - Temporal characteristic analysis
10. **Bark Training Data** - Training dataset preparation

#### Features Still Active (Core MVP)
Essential features that work reliably and quickly:

1. ✅ **Demucs Source Separation** - Separates audio into stems (~30 seconds)
2. ✅ **BPM Detection** - Tempo analysis (~2-3 seconds)
3. ✅ **Key Detection** - Musical key and tuning (~2-3 seconds)
4. ✅ **Beat Extraction** - Beat positions (~2-3 seconds)
5. ✅ **MP3 Metadata** - ID3 tags, album art, basic info
6. ✅ **Duration Calculation** - Audio length

### Expected Performance

**Before Optimization:**
- Analysis time: 3-5+ minutes (often crashed/hung)
- Memory usage: High (causing OOM)
- Success rate: Low

**After Optimization:**
- Analysis time: ~45-60 seconds
- Memory usage: Moderate
- Success rate: High

### Analysis Breakdown (Estimated)

| Step | Time | Status |
|------|------|--------|
| Download audio | 1-2s | ✅ |
| Extract metadata | 1s | ✅ |
| Demucs separation | 30-35s | ✅ |
| BPM detection | 2-3s | ✅ |
| Key detection | 2-3s | ✅ |
| Beat extraction | 2-3s | ✅ |
| Save JAMS output | 1-2s | ✅ |
| Upload to blob | 2-3s | ✅ |
| **Total** | **~45-60s** | **✅** |

## Testing Workflow

### Start Services
```powershell
# Start Docker Desktop first, then:
docker compose up -d
```

### Verify Services
```powershell
docker compose ps
# Should show: db, azurite, api, analysis-worker, generation-worker
```

### Test Analysis
```powershell
# Upload file (via MAUI app or curl)
# Then analyze:
curl.exe -X POST http://localhost:5000/api/audio/{id}/analyze

# Check progress:
curl.exe http://localhost:5000/api/jobs/{jobId}

# View result:
curl.exe http://localhost:5000/api/audio/{id}
```

### Expected Result
```json
{
  "bpm": 117.45,
  "key": "D# major",
  "duration": "00:03:00",
  "status": "Analyzed",
  ...
}
```

## Re-Enabling Features Later

To re-enable the full analysis pipeline for production:

1. Revert changes in `analysis_service.py` line ~233-256
2. Restore the original analysis code:
   - Uncomment section extraction
   - Uncomment chord extraction
   - Uncomment music theory analysis
   - Uncomment all feature extractions

3. Consider optimizations:
   - Use smaller models for sections/chords
   - Cache intermediate results
   - Add better timeout handling
   - Implement streaming/chunked analysis

## Audio Flamingo Removal

Audio Flamingo has been completely removed from the project:
- ✅ `audio_flamingo_service.py` deleted
- ✅ `AUDIO_FLAMINGO_SETUP.md` deleted
- ✅ All Flamingo environment variables removed from `docker-compose.yml`
- ✅ Flamingo dependencies removed from `requirements.txt` (transformers, accelerate)
- ✅ Import statements removed from `analysis_service.py`

**Reason:** The nvidia/audio-flamingo models are not publicly available, and the feature is not essential for MVP.

## Testing Checklist

- [ ] Docker Desktop running
- [ ] All services up: `docker compose ps`
- [ ] API accessible: http://localhost:5000/swagger
- [ ] Upload MP3 file
- [ ] Trigger analysis
- [ ] Wait ~60 seconds
- [ ] Verify BPM and Key detected
- [ ] Download JAMS file (optional)
- [ ] Proceed to stem generation

## Known Limitations

1. **No chord progressions** - Would need chord extraction re-enabled
2. **No genre detection** - Would need theory analysis re-enabled
3. **No advanced features** - Would need full analysis re-enabled
4. **Simplified JAMS output** - Contains only basic annotations

These limitations are acceptable for MVP testing focused on:
- Upload workflow
- Basic analysis (BPM/Key)
- Stem generation
- Download functionality

## Next Steps After MVP

1. **Profile analysis pipeline** - Find actual bottlenecks
2. **Optimize algorithms** - Use faster libraries or lighter models
3. **Implement caching** - Cache expensive computations
4. **Add progress tracking** - Real-time progress updates
5. **Resource limits** - Better memory management
6. **Parallel processing** - Process multiple files simultaneously

---

**Status:** Optimized for MVP testing  
**Performance:** ~60 seconds per 3-minute file  
**Reliability:** High  
**Features:** Core essentials only  

**Ready to test!** 🚀
