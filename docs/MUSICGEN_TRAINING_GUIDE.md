# High-Fidelity AI Music Generation with MusicGen

## Overview

Complete modular pipeline for training and deploying custom MusicGen models with:
- **Custom dataset training** on your music collection
- **LoRA fine-tuning** for efficient adaptation
- **TorchScript/ONNX export** for optimized deployment
- **REST API integration** with .NET MAUI frontend
- **Low-latency inference** with GPU acceleration

---

## Architecture

```
┌─────────────────────┐
│   MAUI Frontend     │
│  (Dataset Upload)   │
└──────────┬──────────┘
           │ HTTP/REST
           ▼
┌─────────────────────┐
│   .NET API          │
│  (Training Jobs)    │
└──────────┬──────────┘
           │ Service Bus
           ▼
┌─────────────────────┐
│  Training Worker    │
│  - Data Prep        │
│  - LoRA Fine-Tuning │
│  - Model Export     │
└──────────┬──────────┘
           │ Blob Storage
           ▼
┌─────────────────────┐
│ Generation Worker   │
│  - Load Trained     │
│  - Generate Audio   │
│  - HiFi Output      │
└─────────────────────┘
```

---

## Components

### 1. Dataset Preprocessing (`dataset_preprocessor.py`)

**Purpose**: Prepare audio files for training

**Features**:
- Load WAV/MP3/FLAC files (any sample rate)
- Resample to 32kHz (MusicGen native)
- Convert stereo → mono
- Normalize amplitude
- Pair with text prompts
- Create training manifest

**Usage**:
```python
from dataset_preprocessor import AudioDataPreprocessor, MusicGenDataset

# Preprocess raw audio directory
preprocessor = AudioDataPreprocessor(
    target_sample_rate=32000,
    target_duration=30.0
)

preprocessor.preprocess_directory(
    input_dir=Path("./raw_audio"),
    output_dir=Path("./preprocessed"),
    create_manifest=True
)

# Load as PyTorch dataset
from transformers import AutoProcessor

processor = AutoProcessor.from_pretrained("facebook/musicgen-small")

dataset = MusicGenDataset.from_directory(
    data_dir=Path("./preprocessed"),
    processor=processor,
    max_duration_seconds=30.0
)
```

**Manifest Format** (`manifest.json`):
```json
[
  {
    "audio": "track001.wav",
    "prompt": "upbeat rock guitar with heavy distortion"
  },
  {
    "audio": "track002.wav",
    "prompt": "slow jazz piano with smooth chord progressions"
  }
]
```

---

### 2. LoRA Fine-Tuning (`musicgen_lora_trainer.py`)

**Purpose**: Efficiently fine-tune MusicGen on custom music

**Why LoRA?**
- **90% fewer parameters** to train vs full fine-tuning
- **Lower GPU memory** requirements (can train on 16GB VRAM)
- **Faster training** (3-5x speedup)
- **Modular adapters** (swap styles without retraining base model)

**Architecture**:
- Base Model: `facebook/musicgen-small` (300M params)
- LoRA Adapters: 16-rank on attention layers (~5M params)
- Training: Mixed precision FP16 with gradient accumulation

**Usage - Hugging Face Trainer**:
```python
from musicgen_lora_trainer import MusicGenLoRATrainer

# Initialize trainer
trainer = MusicGenLoRATrainer(
    base_model_name="facebook/musicgen-small",
    lora_r=16,           # LoRA rank
    lora_alpha=32,       # Scaling factor
    lora_dropout=0.1     # Regularization
)

# Train
metrics = trainer.train(
    train_dataset=train_dataset,
    val_dataset=val_dataset,
    output_dir=Path("./checkpoints"),
    num_epochs=10,
    batch_size=4,
    learning_rate=1e-4,
    gradient_accumulation_steps=4,
    fp16=True
)

# Save trained model
trainer.save_model(Path("./final_model"))
```

**Usage - PyTorch Lightning** (Advanced):
```python
from torch.utils.data import DataLoader
from musicgen_lora_trainer import train_with_pytorch_lightning

# Prepare dataloaders
train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=4)

# Train with Lightning
metrics = train_with_pytorch_lightning(
    peft_model=trainer.peft_model,
    train_dataloader=train_loader,
    val_dataloader=val_loader,
    output_dir=Path("./checkpoints"),
    max_epochs=10,
    learning_rate=1e-4,
    accelerator="gpu",
    devices=1,
    precision="16-mixed"
)
```

**Training Hyperparameters**:
| Parameter | Recommended | Description |
|-----------|-------------|-------------|
| LoRA Rank (r) | 8-32 | Higher = more capacity, slower training |
| LoRA Alpha | 2×r | Scaling factor (typically 2× rank) |
| Learning Rate | 1e-4 | Use 1e-5 for larger datasets |
| Batch Size | 4-8 | Limited by GPU memory |
| Gradient Accumulation | 4-8 | Simulate larger batches |
| Max Duration | 30s | Longer clips = more memory |
| Epochs | 5-15 | Monitor validation loss |

**Expected Training Time** (NVIDIA A100):
- 100 tracks × 30s each = ~50 minutes per epoch
- 10 epochs = **~8 hours total**

---

### 3. Model Export (`model_export.py`)

**Purpose**: Export trained models for production deployment

**Formats**:

#### TorchScript
- **Best for**: Python services, PyTorch inference
- **Benefits**: Native PyTorch, easy integration
- **File size**: ~300 MB (base model)

```python
from model_export import MusicGenExporter

exporter = MusicGenExporter(trained_model, processor)

torchscript_path = exporter.export_to_torchscript(
    output_path=Path("./model.pt"),
    optimize_for_mobile=False
)
```

#### ONNX
- **Best for**: Cross-platform, cloud inference, edge devices
- **Benefits**: Runs on CPU/GPU with ONNX Runtime
- **File size**: ~300 MB (FP32), ~75 MB (INT8 quantized)

```python
onnx_path = exporter.export_to_onnx(
    output_path=Path("./model.onnx"),
    opset_version=14,
    quantize=True  # Enable INT8 quantization
)
```

#### ONNX Inference
```python
from model_export import ONNXInferenceEngine

engine = ONNXInferenceEngine(
    onnx_model_path=Path("./model.onnx"),
    processor_path=Path("./processor"),
    use_gpu=True
)

audio = engine.generate(
    prompt="energetic rock music with electric guitar",
    max_length=1024
)
```

**Quantization Benefits**:
- 75% size reduction (300 MB → 75 MB)
- 2-3× faster CPU inference
- Minimal quality loss (<1% difference)

---

## Training Workflow

### Step 1: Prepare Dataset

1. **Collect Audio Files**
   - Place WAV/MP3 files in `./raw_audio/`
   - Any sample rate (will be resampled to 32kHz)
   - Stereo or mono
   - Recommended: 30-second clips

2. **Preprocess**
   ```bash
   python dataset_preprocessor.py \
     --input-dir ./raw_audio \
     --output-dir ./preprocessed \
     --target-sr 32000 \
     --duration 30.0
   ```

3. **Edit Manifest**
   - Open `./preprocessed/manifest.json`
   - Add descriptive prompts for each track:
   ```json
   {
     "audio": "my_song.wav",
     "prompt": "upbeat electronic dance music with synthesizers"
   }
   ```

### Step 2: Train Model

```python
from musicgen_lora_trainer import MusicGenLoRATrainer
from dataset_preprocessor import MusicGenDataset
from transformers import AutoProcessor

# Load processor
processor = AutoProcessor.from_pretrained("facebook/musicgen-small")

# Load dataset
train_dataset = MusicGenDataset.from_directory(
    data_dir=Path("./preprocessed"),
    processor=processor
)

# Initialize trainer
trainer = MusicGenLoRATrainer(
    base_model_name="facebook/musicgen-small",
    lora_r=16,
    lora_alpha=32
)

# Train
trainer.train(
    train_dataset=train_dataset,
    output_dir=Path("./checkpoints"),
    num_epochs=10,
    batch_size=4,
    learning_rate=1e-4
)
```

### Step 3: Export Model

```python
from model_export import export_trained_model_from_checkpoint

exported = export_trained_model_from_checkpoint(
    checkpoint_path=Path("./checkpoints/final_model"),
    output_dir=Path("./exported"),
    formats=["torchscript", "onnx"]
)
```

### Step 4: Deploy to Generation Worker

Upload exported model to Azure Blob Storage:
```bash
az storage blob upload-batch \
  --account-name azstmo6rlbmgpkrs4 \
  --destination models \
  --source ./exported/ \
  --pattern "model_<UUID>/*"
```

---

## Generation API

### Current Generation Worker Integration

The generation worker (`workers/generation/generation_service.py`) already supports trained models:

```python
# Generate with trained model
await generation_service.generate_track(
    parameters={
        "trained_model_id": "550e8400-e29b-41d4-a716-446655440000",
        "prompt": "epic orchestral music with strings",
        "duration_seconds": 30.0,
        "target_bpm": 120
    },
    output_dir=Path("./output")
)
```

### Supported Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `trained_model_id` | UUID | Trained model to use | `"550e8400-..."` |
| `prompt` | string | Text description | `"upbeat rock guitar"` |
| `duration_seconds` | float | Audio length | `30.0` |
| `target_bpm` | int | Target tempo | `120` |
| `style` | string | Musical style | `"rock"` |
| `key` | string | Musical key | `"C"` |
| `scale` | string | Scale type | `"major"` |
| `temperature` | float | Randomness | `1.0` (0-2) |
| `random_seed` | int | Reproducibility | `42` |

---

## Performance Optimization

### Inference Speed

**Base Model (No Training)**:
- GPU (A100): ~5 seconds for 30s audio
- GPU (RTX 3090): ~8 seconds for 30s audio
- CPU: ~60 seconds for 30s audio

**With Caching**:
```python
class GenerationService:
    def __init__(self):
        self.loaded_models = {}  # Cache loaded models
        
    async def _load_trained_model(self, model_id: str):
        if model_id in self.loaded_models:
            return self.loaded_models[model_id]  # Use cached
        
        # Load from blob storage
        model = await self._download_and_load(model_id)
        self.loaded_models[model_id] = model
        return model
```

### Batch Generation

Generate multiple tracks in parallel:
```python
import asyncio

async def batch_generate(prompts: list):
    tasks = [
        generation_service.generate_track({"prompt": p})
        for p in prompts
    ]
    return await asyncio.gather(*tasks)

# Generate 4 tracks simultaneously
prompts = [
    "rock guitar",
    "jazz piano",
    "electronic synth",
    "orchestral strings"
]

tracks = await batch_generate(prompts)
```

### GPU Memory Management

For multiple concurrent requests:
```python
# Limit concurrent generations
semaphore = asyncio.Semaphore(2)  # Max 2 concurrent

async def generate_with_limit(params):
    async with semaphore:
        return await generation_service.generate_track(params)
```

---

## Integration with .NET API

### Database Models (Add to Domain)

```csharp
public class TrainedModel
{
    public Guid Id { get; set; }
    public string Name { get; set; }
    public string Description { get; set; }
    public Guid TrainingDatasetId { get; set; }
    public virtual TrainingDataset TrainingDataset { get; set; }
    public DateTime TrainedAt { get; set; }
    public string BlobUrl { get; set; }
    public int Epochs { get; set; }
    public float FinalLoss { get; set; }
    public string ModelFormat { get; set; } // "lora", "torchscript", "onnx"
}

public class TrainingJob
{
    public Guid Id { get; set; }
    public Guid TrainingDatasetId { get; set; }
    public virtual TrainingDataset TrainingDataset { get; set; }
    public string Status { get; set; } // "pending", "training", "completed", "failed"
    public DateTime CreatedAt { get; set; }
    public DateTime? StartedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public int CurrentEpoch { get; set; }
    public int TotalEpochs { get; set; }
    public float? CurrentLoss { get; set; }
    public string? ErrorMessage { get; set; }
}
```

### API Endpoints (Add to GenerationController)

```csharp
[HttpPost("train")]
public async Task<ActionResult<TrainingJobResponse>> StartTraining(
    [FromBody] StartTrainingRequest request)
{
    var trainingJob = new TrainingJob
    {
        Id = Guid.NewGuid(),
        TrainingDatasetId = request.DatasetId,
        Status = "pending",
        TotalEpochs = request.Epochs
    };
    
    _context.TrainingJobs.Add(trainingJob);
    await _context.SaveChangesAsync();
    
    // Send to Service Bus training queue
    await _serviceBusClient.SendMessageAsync(
        queueName: "training-jobs",
        message: JsonSerializer.Serialize(trainingJob)
    );
    
    return Ok(new TrainingJobResponse { JobId = trainingJob.Id });
}

[HttpGet("training/{jobId}/status")]
public async Task<ActionResult<TrainingJobStatus>> GetTrainingStatus(Guid jobId)
{
    var job = await _context.TrainingJobs.FindAsync(jobId);
    
    return Ok(new TrainingJobStatus
    {
        Status = job.Status,
        CurrentEpoch = job.CurrentEpoch,
        TotalEpochs = job.TotalEpochs,
        CurrentLoss = job.CurrentLoss
    });
}

[HttpGet("models")]
public async Task<ActionResult<List<TrainedModelDto>>> GetTrainedModels()
{
    var models = await _context.TrainedModels
        .Include(m => m.TrainingDataset)
        .ToListAsync();
    
    return Ok(models.Select(m => new TrainedModelDto
    {
        Id = m.Id,
        Name = m.Name,
        Description = m.Description,
        TrainedAt = m.TrainedAt
    }));
}
```

---

## Next Steps

### TODO

1. ✅ Dataset preprocessing pipeline
2. ✅ LoRA fine-tuning service
3. ✅ Model export (TorchScript/ONNX)
4. ⏳ Training worker service (FastAPI)
5. ⏳ .NET API integration
6. ⏳ Inference optimization
7. ⏳ HiFi-GAN vocoder integration
8. ⏳ MAUI UI for training

### Priority Tasks

1. **Create Training Worker**
   - FastAPI service
   - Service Bus listener for training jobs
   - Progress callbacks to API
   - Checkpoint upload to blob storage

2. **Add Database Migrations**
   - TrainedModel table
   - TrainingJob table
   - TrainingDataset updates

3. **MAUI Frontend**
   - Training dataset upload page
   - Training job creation form
   - Model selection dropdown for generation
   - Training progress visualization

4. **Optimize Inference**
   - Model caching
   - Batch generation
   - GPU memory management
   - ONNX Runtime integration

---

## Resources

- **MusicGen Paper**: https://arxiv.org/abs/2306.05284
- **LoRA Paper**: https://arxiv.org/abs/2106.09685
- **Hugging Face Models**: https://huggingface.co/facebook/musicgen-small
- **PEFT Documentation**: https://huggingface.co/docs/peft
- **PyTorch Lightning**: https://lightning.ai/docs/pytorch/stable/

---

## Support

For questions or issues, check:
1. Training logs in `./checkpoints/logs/`
2. TensorBoard: `tensorboard --logdir ./checkpoints/logs`
3. Model validation metrics in training output
4. ONNX model validation with `onnx.checker`

**Common Issues**:
- **Out of Memory**: Reduce batch size or max_duration
- **Slow Training**: Enable fp16, increase gradient_accumulation_steps
- **Poor Quality**: Increase LoRA rank, train for more epochs
- **Export Fails**: Ensure LoRA weights are merged before export
