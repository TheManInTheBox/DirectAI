# Music Analysis Worker

FastAPI-based microservice for audio source separation and Music Information Retrieval (MIR) analysis.

## Features

### Source Separation
- **Demucs** (htdemucs model) - Separates audio into stems:
  - Vocals
  - Drums  
  - Bass
  - Other (guitar, keys, etc.)

### MIR Analysis
- **Tempo Detection** (BPM) - Using librosa beat tracking
- **Key Detection** - Chromagram-based key estimation
- **Beat Detection** - Frame-accurate beat positions
- **Section Detection** - Structural segmentation (intro, verse, chorus, etc.)
- **Chord Detection** - Basic chord progression analysis
- **Tuning Detection** - Reference frequency (A4)

### Output Format
- **JAMS Annotations** - JSON format following JAMS schema
- **Separated Stems** - WAV files uploaded to blob storage
- **Metadata** - Comprehensive analysis results

---

## API Endpoints

### `GET /health`
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T12:00:00",
  "services": {
    "demucs": "available",
    "essentia": "available",
    "madmom": "available",
    "storage": "connected"
  }
}
```

### `POST /analyze`
Analyze audio file

**Request:**
```json
{
  "audio_file_id": "123e4567-e89b-12d3-a456-426614174000",
  "blob_uri": "http://azurite:10000/devstoreaccount1/audio-files/song.mp3",
  "callback_url": "http://api:8080/api/audio/analysis-callback"
}
```

**Response (Immediate):**
```json
{
  "audio_file_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "message": "Analysis started. Results will be available shortly."
}
```

**Callback Payload (When Complete):**
```json
{
  "audio_file_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "processing_time_seconds": 45.3,
  "analysis": {
    "bpm": 120.5,
    "key": "C",
    "tuning_frequency": 440.0,
    "sections": [...],
    "chords": [...],
    "beats": [...]
  },
  "stems": [
    {
      "stem_type": "vocals",
      "blob_url": "http://azurite:10000/.../vocals.wav",
      "file_size_bytes": 5242880
    }
  ],
  "jams_url": "http://azurite:10000/.../annotation.jams"
}
```

---

## Environment Variables

```bash
# Azure Storage (Required)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;...
# OR
AZURE_STORAGE_ACCOUNT_URL=https://{account}.blob.core.windows.net

# Container name
BLOB_CONTAINER_NAME=audio-files

# Demucs model selection
DEMUCS_MODEL=htdemucs  # Options: htdemucs, htdemucs_ft, mdx_extra

# Worker configuration
WORKERS=1
```

---

## Local Development

### Prerequisites
- Python 3.11+
- FFmpeg installed
- Docker (optional)

### Setup
```bash
cd workers/analysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
```

### Run Locally
```bash
# Start Azurite first
docker run -p 10000:10000 mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0

# Run worker
python main.py
```

Worker will be available at `http://localhost:8080`

---

## Docker

### Build Image
```bash
docker build -t music-analysis-worker .
```

### Run Container
```bash
docker run -p 8080:8080 \
  -e AZURE_STORAGE_CONNECTION_STRING="..." \
  -e BLOB_CONTAINER_NAME=audio-files \
  music-analysis-worker
```

### With Docker Compose
```bash
# From repository root
docker-compose up analysis-worker
```

---

## Processing Pipeline

1. **Download Audio** - Fetch MP3 from blob storage
2. **Source Separation** - Run Demucs to extract stems (vocals, drums, bass, other)
3. **MIR Analysis** - Extract tempo, key, beats, sections, chords
4. **JAMS Generation** - Create standardized annotation format
5. **Upload Results** - Push stems and JAMS to blob storage
6. **Callback** - POST results to API callback URL

**Typical Processing Time:**
- 3-minute song: ~30-60 seconds (CPU)
- 3-minute song: ~15-30 seconds (GPU)

---

## Models Used

### Demucs (htdemucs)
- **Paper:** "Hybrid Transformers for Music Source Separation" (Meta AI)
- **Architecture:** Hybrid CNN + Transformer
- **Quality:** State-of-the-art source separation (2023)
- **Size:** ~800 MB model download on first run

### Librosa
- Beat tracking via dynamic programming
- Chromagram-based key detection
- Structural segmentation

### JAMS Format
- Standard music annotation format
- Compatible with mir_eval, librosa, and other MIR tools
- JSON-based for easy parsing

---

## Performance Considerations

### CPU Mode (Default)
- Single worker recommended
- Processing time: 2-3x realtime
- Memory: ~2-4 GB per worker

### GPU Mode (Optional)
- Requires NVIDIA GPU with CUDA
- 5-10x faster than CPU
- Memory: ~4-8 GB GPU RAM

### Scaling
- Stateless service - can scale horizontally
- Each worker handles one analysis at a time
- Background task processing prevents blocking

---

## Error Handling

All errors are logged and returned via callback:

```json
{
  "audio_file_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "failed",
  "error": "Error message details"
}
```

Common errors:
- Blob download failed (invalid URI, network issue)
- Demucs processing failed (corrupted audio, unsupported format)
- Upload failed (storage connectivity)

---

## Testing

### Health Check
```bash
curl http://localhost:8080/health
```

### Analyze Request
```bash
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "audio_file_id": "test-123",
    "blob_uri": "http://azurite:10000/devstoreaccount1/audio-files/test.mp3"
  }'
```

### View Logs
```bash
docker-compose logs -f analysis-worker
```

---

## Troubleshooting

### "Demucs model not found"
First run downloads ~800 MB model. Ensure internet connectivity and disk space.

### "Blob storage connection failed"
Check `AZURE_STORAGE_CONNECTION_STRING` is correct and Azurite is running.

### "FFmpeg not found"
Ensure FFmpeg is installed in the Docker image (included in Dockerfile).

### Slow processing
- CPU mode is 2-3x realtime (normal)
- Consider GPU deployment for production
- Reduce audio length for testing

---

## Future Enhancements

- [ ] GPU support with CUDA
- [ ] Additional models (Spleeter, Open-Unmix)
- [ ] Advanced chord detection (madmom RNNChordRecognition)
- [ ] Melody extraction
- [ ] Instrument detection
- [ ] Genre classification
- [ ] Audio quality assessment
- [ ] Batch processing support

---

## License

See main repository LICENSE file.
