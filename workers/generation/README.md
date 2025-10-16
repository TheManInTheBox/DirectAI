# Music Generation Worker

FastAPI-based microservice for AI-powered audio stem generation using Stable Audio Open and MusicGen.

## Features

### AI Models Supported
- **MusicGen** (Meta AI) - Text-to-music generation with style control
- **Stable Audio Open** (Stability AI) - High-quality audio generation (placeholder)
- **Mock Mode** - Synthetic waveform generation for testing without models

### Stem Types
- Vocals
- Drums (kick, snare, hi-hat patterns)
- Bass (sub-bass frequencies)
- Guitar (harmonic distortion)
- Piano (chord progressions)
- Synth (pad sounds)
- Other

### Conditioning Parameters
- **Target BPM** - Tempo control
- **Duration** - Generated audio length
- **Style** - Musical genre/style
- **Chord Progression** - Harmonic structure
- **Text Prompt** - Natural language description
- **Temperature** - Randomness control (0.0-2.0)
- **Random Seed** - Reproducibility

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
    "stable_audio": "not_loaded",
    "musicgen": "available",
    "storage": "connected",
    "mode": "mock"
  },
  "gpu_available": false
}
```

### `POST /generate`
Generate audio stems

**Request:**
```json
{
  "generation_request_id": "gen-123e4567-e89b-12d3-a456-426614174000",
  "audio_file_id": "aud-123e4567-e89b-12d3-a456-426614174000",
  "target_stems": ["guitar", "bass", "drums"],
  "parameters": {
    "target_bpm": 120.0,
    "duration_seconds": 30.0,
    "style": "rock",
    "chord_progression": ["C", "G", "Am", "F"],
    "prompt": "energetic rock guitar with distortion",
    "temperature": 1.0,
    "random_seed": 42
  },
  "callback_url": "http://api:8080/api/generation/callback"
}
```

**Response (Immediate):**
```json
{
  "generation_request_id": "gen-123e4567...",
  "status": "processing",
  "message": "Generation started. Stems will be available shortly."
}
```

**Callback Payload (When Complete):**
```json
{
  "generation_request_id": "gen-123e4567...",
  "audio_file_id": "aud-123e4567...",
  "status": "completed",
  "processing_time_seconds": 15.3,
  "generated_stems": [
    {
      "stem_type": "guitar",
      "blob_url": "http://azurite:10000/.../guitar.wav",
      "file_size_bytes": 2621440,
      "format": "wav",
      "sample_rate": 44100,
      "channels": 2
    }
  ],
  "parameters": { ... }
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

# GPU support (requires NVIDIA GPU + CUDA)
USE_GPU=false

# Mock mode (testing without downloading AI models)
MOCK_GENERATION=true

# Worker configuration
WORKERS=1
```

---

## Modes of Operation

### 1. Mock Mode (Default - No GPU Required)
**Best for:** Local testing, CI/CD, development without GPU

```bash
MOCK_GENERATION=true
```

- Generates synthetic waveforms (sine waves, patterns)
- No AI model downloads (~5GB+ saved)
- Fast processing (<1 second per stem)
- Perfect for testing API integration

**Generated Audio:**
- Drums: Kick drum patterns at target BPM
- Bass: Sub-bass frequencies
- Guitar: Harmonic waveforms with distortion
- Vocals: Formant-like frequencies with vibrato
- Piano: Chord progressions with decay envelope
- Synth: Multi-harmonic pad sounds

### 2. MusicGen Mode (CPU/GPU)
**Best for:** Production use with good quality

```bash
MOCK_GENERATION=false
USE_GPU=true  # or false for CPU
```

- Uses Meta AI's MusicGen model
- Text-to-music generation
- Supports style and prompt conditioning
- Model size: ~1.5GB (musicgen-small)
- Processing: 10-30 seconds per 10s audio (GPU)

### 3. Full AI Mode (GPU Recommended)
**Best for:** High-quality production audio

```bash
MOCK_GENERATION=false
USE_GPU=true
```

- MusicGen + Stable Audio Open
- Highest quality generation
- Model size: ~5-10GB total
- Requires significant GPU memory (8GB+)

---

## Local Development

### Prerequisites
- Python 3.11+
- FFmpeg installed
- Docker (optional)
- NVIDIA GPU + CUDA (optional, for AI models)

### Setup
```bash
cd workers/generation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
# Set MOCK_GENERATION=true for testing
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
docker build -t music-generation-worker .
```

### Run Container (Mock Mode)
```bash
docker run -p 8080:8080 \
  -e AZURE_STORAGE_CONNECTION_STRING="..." \
  -e BLOB_CONTAINER_NAME=audio-files \
  -e MOCK_GENERATION=true \
  music-generation-worker
```

### Run Container (GPU Mode)
```bash
docker run --gpus all -p 8080:8080 \
  -e AZURE_STORAGE_CONNECTION_STRING="..." \
  -e BLOB_CONTAINER_NAME=audio-files \
  -e MOCK_GENERATION=false \
  -e USE_GPU=true \
  music-generation-worker
```

### With Docker Compose
```bash
# From repository root
docker-compose up generation-worker
```

---

## Processing Pipeline

```
1. POST /generate
   ↓
2. Validate request (stems, parameters)
   ↓
3. Start background task
   ↓
4. For each target stem:
   a. Build text prompt from parameters
   b. Generate audio (AI model or mock)
   c. Save as WAV (44.1kHz stereo)
   d. Upload to blob storage
   ↓
5. Collect all generated stems
   ↓
6. POST callback to API with results
   ↓
7. Cleanup temporary files
```

**Processing Time:**
- Mock mode: <1 second per stem
- MusicGen (GPU): 10-30 seconds per 10s audio
- MusicGen (CPU): 60-180 seconds per 10s audio

---

## AI Models

### MusicGen (Meta AI)
**Paper:** "Simple and Controllable Music Generation"

**Models Available:**
- `musicgen-small` (300M params) - Fast, good quality
- `musicgen-medium` (1.5B params) - Better quality
- `musicgen-large` (3.3B params) - Best quality

**Features:**
- Text-to-music generation
- Style conditioning
- Melody conditioning
- Multi-track support

**Download:** Auto-downloads on first use (~1.5GB for small)

### Stable Audio Open (Stability AI)
**Status:** Placeholder (implementation pending)

**Features:**
- High-quality audio generation
- Long-form generation (up to 47 seconds)
- Text and audio conditioning
- 44.1kHz stereo output

**Note:** Requires separate setup and model download

---

## Performance Considerations

### Mock Mode
- CPU: <1 second per stem
- Memory: ~500 MB
- Disk: No model storage
- Network: No downloads

### MusicGen (CPU)
- Processing: 60-180 seconds per 10s audio
- Memory: 2-4 GB
- Disk: ~1.5GB (model cache)
- First run: Downloads model

### MusicGen (GPU)
- Processing: 10-30 seconds per 10s audio
- Memory: 2-4 GB RAM + 4-6 GB VRAM
- GPU: NVIDIA with CUDA support
- Recommended: RTX 3060+ or better

### Scaling
- Stateless service - horizontally scalable
- One generation request per worker (blocking)
- Recommend: 1-2 workers per GPU

---

## Testing

### Health Check
```bash
curl http://localhost:8080/health
```

### Generate Request (Mock Mode)
```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "generation_request_id": "test-gen-123",
    "audio_file_id": "test-audio-123",
    "target_stems": ["guitar", "bass"],
    "parameters": {
      "target_bpm": 120.0,
      "duration_seconds": 5.0,
      "style": "rock"
    }
  }'
```

### View Logs
```bash
docker-compose logs -f generation-worker
```

---

## Integration with .NET API

### API Configuration
Update `appsettings.Development.json`:
```json
{
  "Workers": {
    "GenerationUrl": "http://localhost:8002"
  }
}
```

### GenerationController TODO Integration
Replace TODO in `GenerationController.cs`:
```csharp
private async Task TriggerGenerationAsync(Guid generationRequestId)
{
    var generationUrl = _configuration["Workers:GenerationUrl"];
    var generation = await _context.GenerationRequests
        .Include(g => g.Parameters)
        .FirstOrDefaultAsync(g => g.Id == generationRequestId);
    
    var request = new
    {
        generation_request_id = generationRequestId.ToString(),
        audio_file_id = generation.AudioFileId.ToString(),
        target_stems = generation.TargetStems.Select(s => s.ToString().ToLower()).ToList(),
        parameters = new
        {
            target_bpm = generation.Parameters.TargetBpm,
            duration_seconds = generation.Parameters.DurationSeconds,
            style = generation.Parameters.Style,
            chord_progression = generation.Parameters.ChordProgression,
            prompt = generation.Parameters.Prompt,
            temperature = generation.Parameters.Temperature,
            random_seed = generation.Parameters.RandomSeed
        },
        callback_url = $"http://api:8080/api/generation/callback"
    };
    
    await _httpClient.PostAsJsonAsync($"{generationUrl}/generate", request);
}
```

---

## Troubleshooting

### "No AI models loaded"
- Expected in mock mode
- Check `MOCK_GENERATION=true` in .env
- To use AI: Set `MOCK_GENERATION=false` and wait for model download

### Model download slow/fails
- MusicGen small: ~1.5GB download
- Requires internet on first run
- Models cached in `~/.cache/huggingface`

### GPU not detected
- Check: `nvidia-smi` shows GPU
- Verify: PyTorch CUDA installed
- Docker: Use `--gpus all` flag

### Out of memory (GPU)
- Use smaller model: `musicgen-small`
- Reduce duration: `duration_seconds`
- Lower temperature: helps slightly
- Use CPU mode instead

---

## Future Enhancements

- [ ] Stable Audio Open full integration
- [ ] Audioldm support
- [ ] Riffusion support
- [ ] Multi-stem co-generation (coherent mix)
- [ ] Style transfer from reference audio
- [ ] Advanced chord conditioning
- [ ] MIDI conditioning
- [ ] Real-time streaming generation
- [ ] Model ensemble (multiple models)
- [ ] Quality assessment metrics

---

## License

See main repository LICENSE file.
