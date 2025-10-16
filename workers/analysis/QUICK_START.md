# Analysis Worker - Quick Start Guide

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)
```powershell
# Start Azurite + Analysis Worker
docker-compose up -d azurite analysis-worker

# View logs
docker-compose logs -f analysis-worker

# Test health check
curl http://localhost:8001/health
```

### Option 2: Local Python (Development)
```powershell
cd workers\analysis

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
# Docker Compose (port 8001)
curl http://localhost:8001/health

# Local Python (port 8080)
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T...",
  "services": {
    "demucs": "available",
    "essentia": "available",
    "madmom": "available",
    "storage": "connected"
  }
}
```

### Analyze Audio (Mock Request)
```powershell
# POST analyze endpoint
curl -X POST http://localhost:8001/analyze `
  -H "Content-Type: application/json" `
  -d '{
    "audio_file_id": "test-123-guid",
    "blob_uri": "http://azurite:10000/devstoreaccount1/audio-files/test.mp3",
    "callback_url": "http://api:8080/api/audio/analysis-callback"
  }'
```

**Expected Response:**
```json
{
  "audio_file_id": "test-123-guid",
  "status": "processing",
  "message": "Analysis started. Results will be available shortly."
}
```

---

## 📁 File Structure
```
workers/analysis/
├── main.py                  # FastAPI application
├── analysis_service.py      # MIR analysis logic
├── storage_service.py       # Azure Blob Storage
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container build
├── .env.example            # Configuration template
├── README.md               # Full documentation
└── test_worker.py          # Unit tests
```

---

## 🔧 Environment Variables

**Local (.env file):**
```bash
# Azurite (local development)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;

# Container name
BLOB_CONTAINER_NAME=audio-files

# Demucs model
DEMUCS_MODEL=htdemucs
```

**Docker Compose (auto-configured):**
- Already set in `docker-compose.yml`
- Uses internal network (azurite:10000)

---

## 📊 Processing Pipeline

```
1. POST /analyze
   ↓
2. Download MP3 from blob storage
   ↓
3. Demucs Source Separation
   - vocals.wav
   - drums.wav
   - bass.wav
   - other.wav
   ↓
4. MIR Analysis (librosa)
   - BPM detection
   - Key detection
   - Beat tracking
   - Section detection
   - Chord detection
   ↓
5. Generate JAMS annotation
   ↓
6. Upload stems + JAMS to blob storage
   ↓
7. POST callback to API with results
```

**Timing:** 30-60 seconds for 3-minute song (CPU)

---

## 🐛 Troubleshooting

### Worker won't start
```powershell
# Check logs
docker-compose logs analysis-worker

# Common issue: Missing dependencies
docker-compose build --no-cache analysis-worker
```

### "Connection refused" on health check
```powershell
# Check if container is running
docker ps | grep analysis-worker

# Check port mapping
netstat -an | findstr "8001"

# Restart service
docker-compose restart analysis-worker
```

### "Blob storage not connected"
```powershell
# Ensure Azurite is running
docker ps | grep azurite

# Test Azurite directly
curl http://localhost:10000/devstoreaccount1?comp=list
```

### Demucs model download slow
- First run downloads ~800 MB model
- Takes 2-5 minutes depending on connection
- Subsequent runs use cached model

---

## 📝 Common Tasks

### Build Docker Image
```powershell
docker-compose build analysis-worker
```

### Rebuild Without Cache
```powershell
docker-compose build --no-cache analysis-worker
```

### View Real-Time Logs
```powershell
docker-compose logs -f analysis-worker
```

### Stop Worker
```powershell
docker-compose stop analysis-worker
```

### Remove Container
```powershell
docker-compose down analysis-worker
```

### Access Worker Shell
```powershell
docker-compose exec analysis-worker /bin/bash
```

---

## 🔗 Service URLs

**Docker Compose:**
- Analysis Worker: `http://localhost:8001`
- Azurite Blob: `http://localhost:10000`
- Internal (container): `http://analysis-worker:8080`

**Local Python:**
- Analysis Worker: `http://localhost:8080`
- Azurite Blob: `http://localhost:10000`

---

## ✅ Verification Checklist

- [ ] Docker Compose builds without errors
- [ ] Health endpoint returns 200 OK
- [ ] Worker logs show "Application startup complete"
- [ ] Azurite connection successful
- [ ] Demucs model loads (first run)
- [ ] FastAPI docs accessible at `/docs`

---

## 📚 Next Steps

1. **Test with real audio file:**
   - Upload MP3 via API
   - Trigger analysis
   - Verify callback received

2. **Integration testing:**
   - Connect .NET API to worker
   - Implement callback handler
   - End-to-end workflow test

3. **Performance testing:**
   - Measure processing time
   - Monitor memory usage
   - Test concurrent requests

---

## 🆘 Need Help?

- **Full Documentation:** `workers/analysis/README.md`
- **Implementation Details:** `docs/ANALYSIS_WORKER_SUMMARY.md`
- **API Reference:** `http://localhost:8001/docs` (Swagger UI)
- **Test Script:** `python workers/analysis/test_worker.py`

---

**Status:** ✅ Worker implemented and ready for testing  
**Next Task:** Build Generation Worker (Task #5)
