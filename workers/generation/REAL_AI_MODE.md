# Generation Worker - Real AI Models Enabled

## ⚠️ Important Changes

**Mock mode has been removed.** The generation worker now **requires** MusicGen (Meta AI) to be loaded.

---

## What Changed

### Removed Features
- ❌ Mock generation mode (synthetic waveforms)
- ❌ `MOCK_GENERATION` environment variable
- ❌ Fallback to synthetic audio
- ❌ Mock waveform generation methods

### Current Behavior
- ✅ **MusicGen is required** - Worker will fail to start if model cannot be loaded
- ✅ **Real AI generation only** - All stems generated with MusicGen
- ✅ **Model download on first run** - Automatically downloads ~1.5GB model
- ✅ **GPU/CPU support** - Configurable via `USE_GPU` environment variable

---

## First Run Requirements

### Model Download
On first startup, MusicGen will download automatically:
- **Size:** ~1.5 GB (musicgen-small model)
- **Location:** `~/.cache/huggingface/` or Docker volume
- **Time:** 2-5 minutes (depending on internet speed)
- **Requirement:** Internet connection

### Docker Volume
The `docker-compose.yml` now includes a persistent cache volume:
```yaml
volumes:
  - musicgen_cache:/root/.cache  # Persists downloaded models
```

This ensures the model is downloaded only once, not on every container restart.

---

## Performance Expectations

### Processing Time (per 10 seconds of audio)
- **GPU Mode:** 10-30 seconds
- **CPU Mode:** 60-180 seconds

### Resource Requirements
- **CPU Mode:** 2-4 GB RAM, 2-4 CPU cores
- **GPU Mode:** 2-4 GB RAM, 4-8 GB VRAM, NVIDIA GPU with CUDA

### For 3 stems (guitar, bass, drums) at 10 seconds each:
- **GPU:** ~1-2 minutes total
- **CPU:** ~3-9 minutes total

---

## Configuration

### Environment Variables (.env or docker-compose.yml)
```bash
# Azure Storage (Required)
AZURE_STORAGE_CONNECTION_STRING=...

# Container name
BLOB_CONTAINER_NAME=audio-files

# GPU support (set to true if NVIDIA GPU available)
USE_GPU=false
```

### Removed Variables
- ~~`MOCK_GENERATION`~~ - No longer used

---

## Health Check Response

**New format (without mock mode):**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T...",
  "services": {
    "stable_audio": "not_loaded",
    "musicgen": "available",        // ✅ Must be "available"
    "storage": "connected",
    "device": "cpu"                  // or "gpu"
  },
  "gpu_available": false
}
```

If `musicgen` shows `"not_loaded"`, the worker **cannot** generate audio and will return errors.

---

## Startup Sequence

### First Run (Model Download)
```
1. Container starts
2. Python dependencies load
3. MusicGen initialization begins
4. 📥 Model downloads from HuggingFace (~1.5 GB)
5. Model loads into memory
6. ✅ Health check returns "healthy"
7. Ready to accept requests
```

**Expected time:** 3-7 minutes (first run only)

### Subsequent Runs (Cached Model)
```
1. Container starts
2. Python dependencies load
3. MusicGen loads from cache
4. ✅ Health check returns "healthy"
5. Ready to accept requests
```

**Expected time:** 30-60 seconds

---

## Testing Commands

### Start Service
```powershell
# Build and start (with model cache)
docker-compose up -d generation-worker

# View logs (watch model download progress)
docker-compose logs -f generation-worker
```

### Health Check
```powershell
# Wait for "musicgen": "available"
curl http://localhost:8002/health
```

### Generate Request (Real AI)
```powershell
curl -X POST http://localhost:8002/generate `
  -H "Content-Type: application/json" `
  -d '{
    "generation_request_id": "test-gen-123",
    "audio_file_id": "test-audio-123",
    "target_stems": ["guitar"],
    "parameters": {
      "target_bpm": 120.0,
      "duration_seconds": 10.0,
      "style": "rock",
      "prompt": "energetic rock guitar"
    }
  }'
```

**Expected response time:** 60-180 seconds (CPU), 10-30 seconds (GPU)

---

## Error Handling

### Model Load Failure
If MusicGen fails to load, the worker will:
1. Log detailed error
2. Raise RuntimeError
3. Container fails health check
4. Service remains unavailable

**Common causes:**
- Insufficient memory (need 2-4 GB RAM)
- Network issues during download
- Disk space insufficient (need 2 GB free)

**Solution:** Check logs with `docker-compose logs generation-worker`

### Generation Failure
If generation fails mid-request:
- Error logged
- Callback sent with error status
- Temporary files cleaned up
- Worker remains healthy for next request

---

## Production Recommendations

### Resource Allocation
**For CPU-only deployment:**
- 4 GB RAM per worker
- 4 CPU cores per worker
- 1-2 workers per node

**For GPU deployment:**
- 4 GB RAM per worker
- 8 GB VRAM per GPU
- 1-2 workers per GPU
- NVIDIA GPU with CUDA 11.8+

### Scaling Strategy
- **Horizontal:** Add more worker containers
- **Vertical:** Use GPU for 5-10x speedup
- **Hybrid:** Mix of CPU workers (baseline) + GPU workers (burst)

### Caching
- Model cache volume is **essential** for performance
- Without cache, every restart = 1.5 GB download + 3-7 min startup
- With cache, restart = 30-60 seconds

---

## Comparison: Before vs After

| Feature | Before (Mock Mode) | After (Real AI) |
|---------|-------------------|-----------------|
| **Startup Time** | <10 seconds | 30-60s (cached) / 3-7min (first) |
| **Processing** | <1 second | 60-180s (CPU) / 10-30s (GPU) |
| **Audio Quality** | Synthetic sine waves | Real AI-generated music |
| **Model Download** | None | 1.5 GB (one-time) |
| **Memory** | 500 MB | 2-4 GB |
| **Fallback** | Always worked | Fails if model can't load |
| **Use Case** | Testing/CI/CD | Production/Real users |

---

## Why This Change?

**Reasons for removing mock mode:**
1. **Production-ready focus** - Building real system, not prototype
2. **Quality matters** - Users expect real AI audio, not test waveforms
3. **Simplified codebase** - Less branching logic, clearer purpose
4. **Realistic testing** - Tests now reflect actual performance
5. **Authentic development** - Experience real constraints early

**Trade-offs accepted:**
- Slower first startup (one-time cost)
- Longer processing times (realistic expectations)
- Resource requirements (plan infrastructure accordingly)

---

## Migration Guide

If you were using mock mode before:

### Update Environment
```bash
# OLD .env
MOCK_GENERATION=true
USE_GPU=false

# NEW .env (remove MOCK_GENERATION)
USE_GPU=false
```

### Rebuild Container
```powershell
docker-compose build --no-cache generation-worker
docker-compose up -d generation-worker
```

### Wait for Model Download
```powershell
# Monitor progress
docker-compose logs -f generation-worker

# Look for: "MusicGen loaded successfully"
```

### Update Expectations
- Integration tests will now take **minutes** instead of seconds
- Budget for 1.5 GB model download
- Plan for 2-4 GB RAM per worker

---

## Next Steps

1. **Start the worker:** `docker-compose up -d generation-worker`
2. **Watch logs:** Monitor model download progress
3. **Test health:** Wait for `"musicgen": "available"`
4. **Generate test:** Send a short generation request (5-10 seconds)
5. **Evaluate performance:** Measure actual processing times

---

**Status:** ✅ Mock mode removed, real AI models required  
**Ready for:** Production-quality audio generation  
**Next:** Proceed with MAUI frontend (Task #6)
