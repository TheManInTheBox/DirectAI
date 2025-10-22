# DirectAI Music Platform

**AI-Powered Music Analysis & Generation Platform** - Production-ready platform for music studios, producers, and enterprises.

> 🚀 **Status:** MVP Complete ✅ | Ready for Azure Deployment

A comprehensive music analysis and generation platform leveraging state-of-the-art AI models (Demucs, MusicGen) to analyze audio structure, separate stems, extract musical features, and generate new music programmatically.

**📘 [Deployment Plan](.azure/plan.copilotmd)** | **🚀 [Quick Start Guide](GET_STARTED.md)** | **📋 [MVP Status](MVP_STATUS.md)**

## ✨ Core Features

### Audio Analysis
- **Stem Separation**: Demucs v4 (htdemucs) - 4-stem isolation (vocals, drums, bass, other)
- **Musical Analysis**: BPM detection, key/scale detection, chord extraction, beat tracking
- **Metadata Extraction**: ID3 tags, album artwork, duration, format
- **Real-Time Updates**: SignalR WebSocket notifications for job progress

### AI Music Generation (MusicGen)
- **Model**: Meta's MusicGen-small (300MB, 8-second load time)
- **Text-to-Music**: Generate music from text prompts
- **Controllable Parameters**: BPM, key, style, duration
- **Training Pipeline**: Fine-tune on custom stems for personalized generation
- **Output**: 32kHz generation, resampled to 44.1kHz WAV

### Production Features
- **Async Job Processing**: Service Bus queues with auto-scaling workers
- **Blob Storage**: Azure Storage for audio files, stems, and training data
- **Database**: PostgreSQL 16 with Entity Framework Core
- **API**: .NET 8.0 REST API with Swagger documentation
- **Cross-Platform UI**: .NET MAUI desktop app (Windows/Mac)

## 🏗️ Architecture

### Technology Stack
- **.NET 8.0**: Web API, Entity Framework, SignalR, MAUI
- **Python Workers**: FastAPI microservices (analysis + generation)
- **AI Models**: Demucs v4, MusicGen, librosa, essentia, madmom
- **Azure**: Container Apps, PostgreSQL, Blob Storage, Service Bus
- **Containerization**: Docker Compose (local), Azure Container Apps (production)

### Local Development
```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   .NET API  │────▶│  PostgreSQL  │     │  Blob Storage   │
│  (Port 5000)│     │  (Port 5432) │     │   (Azurite)     │
└──────┬──────┘     └──────────────┘     └────────┬────────┘
       │                                           │
       ├───────────┬───────────────────────────────┤
       │           │                               │
       ▼           ▼                               ▼
┌─────────────┐ ┌─────────────┐          ┌─────────────┐
│  Analysis   │ │ Generation  │          │   Service   │
│   Worker    │ │   Worker    │          │     Bus     │
│ (Port 8001) │ │ (Port 8080) │          │   Queues    │
└─────────────┘ └─────────────┘          └─────────────┘
```

### Azure Production (Per Customer)
```
Customer Subscription
├── Container Apps Environment
│   ├── API (1-10 replicas, always-on)
│   ├── Analysis Worker (0-5 replicas, auto-scale)
│   └── Generation Worker (0-3 replicas, auto-scale)
├── PostgreSQL Flexible Server (B2s)
├── Blob Storage Account (LRS/GRS)
├── Service Bus Namespace (Standard)
├── Container Registry
├── Application Insights + Log Analytics
├── Key Vault (secrets management)
└── Managed Identity (RBAC security)
```

## 🚀 Quick Start

### Prerequisites
- Docker Desktop
- .NET 8.0 SDK
- Git

### Run Locally
```powershell
# Clone repository
git clone https://github.com/TheManInTheBox/DirectAI.git
cd DirectAI

# Start all services
docker compose up -d

# Check service health
docker compose ps
docker compose logs api --tail=20

# Access services
# API: http://localhost:5000
# Swagger: http://localhost:5000/swagger
# PgAdmin: http://localhost:5050
```

### Deploy to Customer Azure Subscription
```powershell
# Set customer context
azd env new customer-acme-music
azd env set CUSTOMER_NAME "acme-music"
azd env set AZURE_SUBSCRIPTION_ID "customer-sub-id"

# Deploy infrastructure + apps
azd up --subscription "customer-sub-id"

# Verify deployment
azd show
azd monitor --logs
```

**📘 [Full Deployment Guide](.azure/plan.copilotmd)**

## 📊 Current Status (MVP Complete)

✅ **Backend Infrastructure**
- .NET 8.0 API with async job processing
- PostgreSQL database with EF Core migrations
- Blob storage integration (Azurite local, Azure production)
- SignalR real-time job updates

✅ **Analysis Worker**
- Demucs v4 stem separation (~30s per track)
- BPM detection, key/scale analysis
- Chord extraction with timeout handling
- Beat tracking and metadata extraction
- MP3 album artwork support

✅ **Generation Worker**
- MusicGen-small integration (8s startup)
- Text-to-music generation
- 32kHz → 44.1kHz resampling
- Compatible with analysis worker output

✅ **Deployment Ready**
- Docker Compose for local development
- Azure Container Apps deployment plan
- Bicep infrastructure-as-code templates
- Per-customer isolation architecture

🔄 **In Progress**
- Training pipeline for MusicGen fine-tuning
- Stem selection UI for dataset creation
- Parameter-controlled generation (key, BPM, bars)
- Customer onboarding automation

**📋 [Detailed MVP Status](MVP_STATUS.md)** | **🧪 [Testing Guide](MVP_TESTING_STATUS.md)**

## 📚 Documentation

- **[Get Started Guide](GET_STARTED.md)** - Local setup and first analysis job
- **[MVP Status](MVP_STATUS.md)** - Current implementation status and roadmap
- **[Testing Guide](MVP_TESTING_STATUS.md)** - How to test all features
- **[Deployment Plan](.azure/plan.copilotmd)** - Azure Container Apps deployment strategy
- **[Architecture Overview](docs/MUSIC_PLATFORM_ARCHITECTURE.md)** - System design and data flow
- **[API Reference](docs/API_CONTROLLERS_SUMMARY.md)** - REST endpoints documentation
- **[Worker Documentation](docs/WORKERS_COMPLETE_SUMMARY.md)** - Analysis & generation workers

## 🎓 Key Capabilities

### For Music Producers
- Upload tracks → Get separated stems in 30 seconds
- Analyze chord progressions and key signatures
- Extract BPM and beat grids for remixing
- Generate new stems matching your musical style

### For Developers
- RESTful API with OpenAPI/Swagger
- Real-time WebSocket updates via SignalR
- Async job processing with retry logic
- Comprehensive logging and telemetry

### For Enterprises
- Isolated Azure deployment per customer
- Managed identity security (no credentials)
- Auto-scaling workers (cost-efficient)
- Centralized monitoring via Azure Lighthouse

## ️ Development

### Project Structure
```
DirectAI/
├── src/
│   ├── MusicPlatform.Api/          # .NET 8.0 REST API
│   ├── MusicPlatform.Domain/        # Core business logic
│   └── MusicPlatform.Infrastructure/ # Data access, external services
├── workers/
│   ├── analysis/                    # Python FastAPI (Demucs, analysis)
│   └── generation/                  # Python FastAPI (MusicGen)
├── infrastructure/
│   ├── main.bicep                   # Azure IaC templates
│   └── kubernetes/                  # K8s manifests (optional)
├── database/
│   └── schema.sql                   # PostgreSQL schema
├── .azure/
│   └── plan.copilotmd              # Deployment plan
└── docker-compose.yml              # Local development
```

### Running Tests
```powershell
# .NET API tests
dotnet test tests/DirectML.AI.Tests/

# Test analysis worker locally
docker compose up -d analysis-worker
curl http://localhost:8001/health

# Test generation worker locally
docker compose up -d generation-worker
curl http://localhost:8080/health
```

### Building for Production
```powershell
# Build all Docker images
docker compose build

# Push to Azure Container Registry
az acr login --name <registry-name>
docker tag directai-api <registry>.azurecr.io/directai-api:latest
docker push <registry>.azurecr.io/directai-api:latest
```

## 🤝 Contributing

This is a commercial product under active development. For partnership opportunities, licensing, or technical inquiries:

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Architecture and design conversations
- **Pull Requests**: Welcome for bug fixes (requires CLA)

## 📄 License

Proprietary - All rights reserved. Commercial licensing available.

Contact: [GitHub Profile](https://github.com/TheManInTheBox)

---

**Built with:** .NET 8.0 • Python 3.10 • Azure • Docker • PostgreSQL • MusicGen • Demucs

**Powered by:** Meta AI (MusicGen) • FAIR (Demucs) • MTG (Essentia) • madmom
