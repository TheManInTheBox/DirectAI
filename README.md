# DirectML.AI Platform

A comprehensive machine learning suite for .NET providing DirectML-accelerated inference, training, vector database, and semantic search capabilities.

## 🎵 NEW: AI-Powered Music Analysis & Generation Platform

**Status:** Architecture Complete ✅ | Ready for Implementation

We've architected a production-grade music analysis and generation platform built on Azure and .NET 8.0. This system ingests audio files, performs comprehensive musical structure analysis, and generates new stems/loops using state-of-the-art AI models.

**📘 [View Full Architecture](docs/MUSIC_PLATFORM_ARCHITECTURE.md)**  
**🧑‍💼 [Hiring Expert Team Members](docs/HIRING_EXPERTS.md)**  
**📋 [Project Summary](docs/PROJECT_SUMMARY.md)**  
**🚀 [Quick Reference Guide](docs/QUICK_REFERENCE.md)**

### Key Features
- **Audio Analysis Pipeline**: Source separation (Demucs), MIR algorithms (Essentia, madmom)
- **AI Generation**: Stable Audio Open, MusicGen, DiffSinger integration
- **Azure Orchestration**: Durable Functions for stateful workflows
- **Scalable Infrastructure**: AKS with CPU/GPU node pools
- **JAMS-Compliant**: Industry-standard music annotation format

### Technology Stack
- .NET 8.0 (Web API, Durable Functions)
- Azure (AKS, Blob Storage, SQL, OpenAI)
- Python ML (PyTorch, librosa, Demucs)
- Containerization (Docker, Kubernetes)

---

## DirectML.AI Core Features

- **DirectML Acceleration**: Hardware-accelerated ML inference using DirectML
- **Model Management**: Load, cache, and manage ML models efficiently  
- **Inference**: High-performance model inference with streaming support
- **Vector Database**: In-memory vector storage and similarity search
- **Semantic Search**: Natural language text search with embeddings
- **Training**: Model training and fine-tuning capabilities
- **Dependency Injection**: Full .NET DI container support

## Quick Start

### Installation

```bash
dotnet add package DirectML.AI
```

### Basic Usage

```csharp
using DirectML.AI.Extensions;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = Host.CreateApplicationBuilder(args);

// Add DirectML.AI services
builder.Services.AddDirectMLAI(config =>
{
    config.DirectML.Enabled = true;
    config.DirectML.DeviceId = 0;
    config.Models.CacheDirectory = "models";
});

var host = builder.Build();

// Get the AI service
var aiService = host.Services.GetRequiredService<IAIService>();
await aiService.InitializeAsync(new AIConfiguration());

await host.RunAsync();
```

### Inference Example

```csharp
var inferenceProvider = host.Services.GetRequiredService<IInferenceProvider>();

// Load a model
var modelMetadata = new ModelMetadata("my-model", "path/to/model.onnx", "1.0", "transformer", 1024);
await inferenceProvider.LoadModelAsync(modelMetadata);

// Run inference
var request = new InferenceRequest("Hello, world!");
var response = await inferenceProvider.InferAsync(request);

Console.WriteLine($"Output: {response.Output}");
```

## Configuration

The platform can be configured through appsettings.json:

```json
{
  "DirectMLAI": {
    "DirectML": {
      "Enabled": true,
      "DeviceId": 0,
      "MaxMemoryMB": 4096
    },
    "Models": {
      "CacheDirectory": "models",
      "EnableCache": true,
      "MaxCachedModels": 10
    },
    "VectorDatabase": {
      "DefaultDimensions": 384,
      "InMemoryOnly": true,
      "MaxVectors": 1000000
    }
  }
}
```

## License

MIT License
