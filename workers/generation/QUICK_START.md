# Generation Worker - Quick Start Guide

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)
```powershell
# Start Azurite + Generation Worker
docker-compose up -d azurite generation-worker

# View logs
docker-compose logs -f generation-worker

# Test health check
curl http://localhost:8002/health
```

### Option 2: Local Python (Development)
```powershell
cd workers\generation

# Setup virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Run worker
python main.py
```

---

## 🧪 Testing Commands

### Health Check
```powershell
# Docker Compose (port 8002)
curl http://localhost:8002/health

# Local Python (port 8080)
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T...",
  "services": {
    "stable_audio": "not_loaded",
    "musicgen": "not_loaded",
    "storage": "connected",
    "mode": "mock"
  },
  "gpu_available": false
}
```

### Generate Stems (Mock Mode)
```powershell
# POST generate endpoint
curl -X POST http://localhost:8002/generate `
  -H "Content-Type: application/json" `
  -d '{
    "generation_request_id": "test-gen-123",
    "audio_file_id": "test-audio-123",
    "target_stems": ["guitar", "bass", "drums"],
    "parameters": {
      "target_bpm": 120.0,
      "duration_seconds": 10.0,
      "style": "rock",
      "prompt": "energetic rock music"
    }
  }'
```

**Expected Response:**
```json
{
  "generation_request_id": "test-gen-123",
  "status": "processing",
  "message": "Generation started. Stems will be available shortly."
}
```

---

## 📁 File Structure
```
workers/generation/
├── main.py                    # FastAPI application
├── generation_service.py      # AI generation logic
├── storage_service.py         # Azure Blob Storage
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container build
├── .env.example              # Configuration template
├── README.md                 # Full documentation
└── test_worker.py            # Unit tests
```

---

## 🔧 Environment Variables

**Local (.env file):**
```bash
# Azurite (local development)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;

# Container name
BLOB_CONTAINER_NAME=audio-files

# Mode selection
MOCK_GENERATION=true  # true = synthetic audio, false = AI models
USE_GPU=false         # true = CUDA GPU, false = CPU
```

**Docker Compose (auto-configured):**
- Already set in `docker-compose.yml`
- Uses internal network (azurite:10000)
- Mock mode enabled by default

---

## 🎨 Generation Modes

### Mock Mode (Default)
**Fast testing without AI models**

- ✅ No model downloads (saves ~5GB+)
- ✅ <1 second per stem
- ✅ Perfect for integration testing
- ✅ Synthetic waveforms (sine waves, patterns)

**Generated Audio Types:**
- **Drums:** Kick drum patterns at target BPM
- **Bass:** Sub-bass frequencies (55Hz)
- **Guitar:** Harmonic tones with distortion
- **Vocals:** Formant frequencies with vibrato
- **Piano:** Chord progressions with decay
- **Synth:** Multi-harmonic pad sounds

### AI Mode (Production)
**High-quality music generation**

```bash
MOCK_GENERATION=false
USE_GPU=true
```

- Uses MusicGen (Meta AI)
- ~1.5GB model download (first run)
- 10-30 seconds per 10s audio (GPU)
- Text-to-music with style control

---

## 📊 Processing Pipeline

```
1. POST /generate
   ↓
2. Validate stems and parameters
   ↓
3. Start background task
   ↓
4. For each stem:
   a. Build text prompt
   b. Generate audio (AI or mock)
   c. Save as WAV (44.1kHz stereo)
   d. Upload to blob storage
   ↓
5. POST callback with results
   ↓
6. Cleanup temp files
```

**Timing:**
- Mock mode: <1 second per stem
- AI mode (GPU): 10-30 seconds per stem
- AI mode (CPU): 60-180 seconds per stem

---

## 🐛 Troubleshooting

### Worker won't start
```powershell
# Check logs
docker-compose logs generation-worker

# Common issue: Missing dependencies
docker-compose build --no-cache generation-worker
```

### "Connection refused" on health check
```powershell
# Check if container is running
docker ps | grep generation-worker

# Check port mapping
netstat -an | findstr "8002"

# Restart service
docker-compose restart generation-worker
```

### "Blob storage not connected"
```powershell
# Ensure Azurite is running
docker ps | grep azurite

# Test Azurite directly
curl http://localhost:10000/devstoreaccount1?comp=list
```

### Want to use AI models instead of mock
```powershell
# Edit docker-compose.yml or .env
MOCK_GENERATION=false

# Note: First run downloads ~1.5GB MusicGen model
# Requires internet connection
```

---

## 📝 Common Tasks

### Build Docker Image
```powershell
docker-compose build generation-worker
```

### Rebuild Without Cache
```powershell
docker-compose build --no-cache generation-worker
```

### View Real-Time Logs
```powershell
docker-compose logs -f generation-worker
```

### Stop Worker
```powershell
docker-compose stop generation-worker
```

### Access Worker Shell
```powershell
docker-compose exec generation-worker /bin/bash
```

### Run Unit Tests
```powershell
cd workers\generation
python test_worker.py
```

---

## 🔗 Service URLs

**Docker Compose:**
- Generation Worker: `http://localhost:8002`
- Azurite Blob: `http://localhost:10000`
- Internal (container): `http://generation-worker:8080`

**Local Python:**
- Generation Worker: `http://localhost:8080`
- Azurite Blob: `http://localhost:10000`

---

## ✅ Verification Checklist

- [ ] Docker Compose builds without errors
- [ ] Health endpoint returns 200 OK
- [ ] Worker logs show "Application startup complete"
- [ ] Azurite connection successful
- [ ] Mock generation produces WAV files
- [ ] FastAPI docs accessible at `/docs`

---

## 🎯 Stem Types Supported

Valid stem types for `target_stems` array:
- `vocals` - Vocal melodies/harmonies
- `drums` - Drum patterns (kick, snare, hi-hat)
- `bass` - Bass lines
- `guitar` - Guitar parts
- `piano` - Piano/keyboard
- `synth` - Synthesizer pads/leads
- `other` - Other instruments

---

## 📚 Next Steps

1. **Test with mock generation:**
   - Send generate request
   - Verify stems uploaded to Azurite
   - Check callback received by API

2. **Integration testing:**
   - Connect .NET API to worker
   - Implement callback handler
   - End-to-end workflow test

3. **Switch to AI mode (optional):**
   - Set `MOCK_GENERATION=false`
   - Wait for model download (~1.5GB)
   - Test with real AI generation

---

## 🆘 Need Help?

- **Full Documentation:** `workers/generation/README.md`
- **API Reference:** `http://localhost:8002/docs` (Swagger UI)
- **Test Script:** `python workers/generation/test_worker.py`
- **Compare with Analysis Worker:** Similar architecture

---

**Status:** ✅ Worker implemented and ready for testing  
**Mode:** Mock generation (fast, no downloads)  
**Next Task:** Create .NET MAUI Frontend (Task #6)
