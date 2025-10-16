# AI-Powered Music Analysis & Generation Platform
## Architecture Specification v1.0

---

## 📋 Executive Summary

This document outlines the production-grade architecture for an AI-powered music analysis and generation platform built on **.NET 8.0** and **Azure Cloud Services**. The system ingests MP3 files, performs comprehensive musical structure analysis (sections, chords, key, tempo, tuning), stores metadata, and generates new stems/loops using state-of-the-art AI models.

**Key Technologies:**
- **.NET 8.0** (Web API, Durable Functions, Workers)
- **Azure Kubernetes Service (AKS)** for containerized workloads
- **Azure Durable Functions** for stateful orchestration
- **Azure Blob Storage** for audio assets
- **Azure SQL Database / PostgreSQL** for metadata
- **Azure OpenAI** for LLM-based orchestration
- **Python ML Stack** (Demucs, Essentia, madmom, PyTorch models)
- **DirectML.AI** for local GPU-accelerated inference

---

## 🏗️ System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT APPLICATIONS                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Web UI     │  │  Mobile App  │  │   CLI Tool   │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
└─────────┼──────────────────┼──────────────────┼────────────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │ HTTPS/REST
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AZURE API MANAGEMENT (Optional)                     │
│  • Rate Limiting  • Authentication  • Request Transformation             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        .NET CORE WEB API                                 │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  Controllers:                                                   │    │
│  │  • AudioIngestionController  • MetadataController               │    │
│  │  • GenerationController      • HealthController                │    │
│  │                                                                 │    │
│  │  Services:                                                      │    │
│  │  • StorageService  • MetadataService  • OrchestrationService   │    │
│  └────────────────────────────────────────────────────────────────┘    │
└───────────────┬─────────────────────────────────────┬───────────────────┘
                │                                     │
                │ Triggers Workflow                   │ Queries/Writes
                ▼                                     ▼
┌───────────────────────────────────┐  ┌──────────────────────────────────┐
│  AZURE DURABLE FUNCTIONS          │  │    AZURE SQL DATABASE /          │
│  (Orchestration Engine)           │  │    POSTGRESQL                    │
│                                   │  │                                  │
│  ┌─────────────────────────────┐ │  │  • AudioFiles (metadata)        │
│  │  Orchestrator Functions:    │ │  │  • AnalysisResults              │
│  │  • AnalysisOrchestrator     │ │  │  • JAMSAnnotations              │
│  │  • GenerationOrchestrator   │ │  │  • GenerationRequests           │
│  │  • PipelineOrchestrator     │ │  │  • Stems                        │
│  │                             │ │  │  • Jobs (status tracking)       │
│  │  Activity Functions:        │ │  └──────────────────────────────────┘
│  │  • UploadToBlob             │ │
│  │  • TriggerAnalysis          │ │
│  │  • TriggerGeneration        │ │  ┌──────────────────────────────────┐
│  │  • SaveMetadata             │ │  │    AZURE BLOB STORAGE            │
│  │  • NotifyCompletion         │◄─┼─►│                                  │
│  └─────────────────────────────┘ │  │  Container Structure:            │
│                                   │  │  /raw-audio/{id}.mp3             │
└───────┬───────────────────┬───────┘  │  /stems/{id}/vocals.wav          │
        │                   │          │  /stems/{id}/drums.wav           │
        │ Queue Messages    │          │  /stems/{id}/bass.wav            │
        ▼                   ▼          │  /generated/{id}/{stem}.wav      │
┌───────────────┐   ┌──────────────┐  │  /jams/{id}.jams                 │
│ AZURE SERVICE │   │ AZURE EVENT  │  └──────────────────────────────────┘
│     BUS       │   │    GRID      │
│ (Work Queue)  │   │  (Events)    │  ┌──────────────────────────────────┐
└───────┬───────┘   └──────┬───────┘  │    AZURE OPENAI SERVICE          │
        │                  │          │                                  │
        └──────────┬───────┘          │  • GPT-4 (orchestration logic)  │
                   │                  │  • Prompt engineering            │
                   ▼                  │  • Condition generation          │
┌─────────────────────────────────────────────────────────────────────────┐
│                    AZURE KUBERNETES SERVICE (AKS)                        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  ANALYSIS WORKER PODS (CPU-optimized)                          │   │
│  │  • Demucs (source separation)                                  │   │
│  │  • Essentia (MIR: key, tempo, chords)                          │   │
│  │  • madmom (beat tracking, downbeat)                            │   │
│  │  • librosa (spectral analysis)                                 │   │
│  │  • chord-recognition models                                    │   │
│  │  → Outputs JAMS annotations                                    │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  GENERATION WORKER PODS (GPU-required: NVIDIA T4/A10/A100)     │   │
│  │  • Stable Audio Open (stem generation)                         │   │
│  │  • MusicGen (melody/accompaniment)                             │   │
│  │  • DiffSinger (vocal synthesis)                                │   │
│  │  • Conditioning logic (BPM, chord grid, section labels)        │   │
│  │  → Outputs audio stems (WAV/FLAC)                              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  DIRECTML WORKER PODS (DirectML GPU acceleration)              │   │
│  │  • DirectML.AI inference engine                                │   │
│  │  • ONNX Runtime with DirectML provider                         │   │
│  │  • Model format conversion (PyTorch → ONNX)                    │   │
│  │  → Alternative inference path for Windows GPUs                 │   │
│  └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    MONITORING & OBSERVABILITY                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  App Insights    │  │  Log Analytics   │  │  Prometheus/     │     │
│  │  (Distributed    │  │  Workspace       │  │  Grafana         │     │
│  │   Tracing)       │  │                  │  │  (Metrics)       │     │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow Pipeline

### 1. Audio Ingestion Flow

```
User uploads MP3 → API validates format/size → Upload to Blob Storage
                                             → Create job record in DB
                                             → Trigger AnalysisOrchestrator
```

### 2. Analysis Orchestration Flow (Durable Function)

```csharp
// Pseudo-code for AnalysisOrchestrator
[FunctionName("AnalysisOrchestrator")]
public async Task<AnalysisResult> RunOrchestrator(
    [OrchestrationTrigger] IDurableOrchestrationContext context)
{
    var audioFileId = context.GetInput<Guid>();
    
    // Step 1: Source separation (parallel execution)
    var separationTasks = new[]
    {
        context.CallActivityAsync<StemUrls>("SeparateStems", audioFileId),
        context.CallActivityAsync<Metadata>("ExtractBasicMetadata", audioFileId)
    };
    await Task.WhenAll(separationTasks);
    
    // Step 2: Parallel MIR analysis on separated stems
    var analysisResults = await context.CallActivityAsync<MIRResults>(
        "PerformMIRAnalysis", audioFileId);
    
    // Step 3: Structure and chord detection
    var structuralAnalysis = await context.CallActivityAsync<StructuralAnnotations>(
        "DetectStructure", audioFileId);
    
    // Step 4: Convert to JAMS format and save
    var jamsAnnotation = await context.CallActivityAsync<string>(
        "ConvertToJAMS", analysisResults);
    
    // Step 5: Save to database and blob storage
    await context.CallActivityAsync("SaveAnalysisResults", 
        new { audioFileId, jamsAnnotation, analysisResults });
    
    return new AnalysisResult { AudioFileId = audioFileId, Status = "Completed" };
}
```

### 3. Generation Orchestration Flow

```csharp
[FunctionName("GenerationOrchestrator")]
public async Task<GenerationResult> RunOrchestrator(
    [OrchestrationTrigger] IDurableOrchestrationContext context)
{
    var request = context.GetInput<GenerationRequest>();
    
    // Step 1: LLM determines optimal generation strategy
    var strategy = await context.CallActivityAsync<GenerationStrategy>(
        "PlanGenerationStrategy", request);
    
    // Step 2: Prepare conditioning data (BPM, chords, structure)
    var conditioning = await context.CallActivityAsync<ConditioningData>(
        "PrepareConditioning", request.AudioFileId);
    
    // Step 3: Generate stems in parallel (if multiple requested)
    var generationTasks = request.TargetStems.Select(stemType =>
        context.CallActivityAsync<GeneratedStem>(
            "GenerateStem", 
            new { stemType, conditioning, strategy })
    ).ToArray();
    
    var generatedStems = await Task.WhenAll(generationTasks);
    
    // Step 4: Save generated audio
    await context.CallActivityAsync("SaveGeneratedStems", generatedStems);
    
    return new GenerationResult { Stems = generatedStems };
}
```

---

## 🗄️ Data Models

### Domain Models (C#)

```csharp
// Core domain models
public record AudioFile(
    Guid Id,
    string OriginalFileName,
    string BlobUri,
    long SizeBytes,
    TimeSpan Duration,
    string Format,
    DateTime UploadedAt,
    AudioFileStatus Status
);

public record JAMSAnnotation(
    Guid Id,
    Guid AudioFileId,
    string JamsJson, // Full JAMS specification
    DateTime CreatedAt
);

public record AnalysisResult(
    Guid Id,
    Guid AudioFileId,
    float Bpm,
    string Key,
    string Mode,
    float Tuning, // Hz deviation from A440
    List<Section> Sections,
    List<ChordAnnotation> Chords,
    List<BeatAnnotation> Beats,
    DateTime AnalyzedAt
);

public record Section(
    float StartTime,
    float EndTime,
    string Label // verse, chorus, bridge, etc.
);

public record ChordAnnotation(
    float StartTime,
    float EndTime,
    string Chord // e.g., "C:maj", "Am", "G7"
);

public record GenerationRequest(
    Guid Id,
    Guid AudioFileId,
    List<StemType> TargetStems,
    GenerationParameters Parameters,
    DateTime RequestedAt,
    GenerationStatus Status
);

public record GeneratedStem(
    Guid Id,
    Guid GenerationRequestId,
    StemType Type,
    string BlobUri,
    float DurationSeconds,
    DateTime GeneratedAt
);

public enum StemType
{
    Vocals,
    Drums,
    Bass,
    Guitar,
    Piano,
    Synth,
    Other
}

public enum AudioFileStatus
{
    Uploaded,
    Analyzing,
    Analyzed,
    Failed
}

public enum GenerationStatus
{
    Pending,
    Planning,
    Generating,
    Completed,
    Failed
}
```

### Database Schema (SQL)

```sql
-- Audio files metadata
CREATE TABLE AudioFiles (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    OriginalFileName NVARCHAR(255) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    SizeBytes BIGINT NOT NULL,
    DurationMs INT NOT NULL,
    Format NVARCHAR(10) NOT NULL,
    UploadedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    Status NVARCHAR(20) NOT NULL,
    INDEX IX_UploadedAt (UploadedAt),
    INDEX IX_Status (Status)
);

-- JAMS annotations (JSON storage)
CREATE TABLE JAMSAnnotations (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    JamsJson NVARCHAR(MAX) NOT NULL, -- JSON column for JAMS spec
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_AudioFileId (AudioFileId)
);

-- Analysis results (queryable metadata)
CREATE TABLE AnalysisResults (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    Bpm FLOAT NOT NULL,
    MusicalKey NVARCHAR(10) NOT NULL,
    Mode NVARCHAR(10) NOT NULL,
    Tuning FLOAT NOT NULL,
    AnalyzedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_AudioFileId (AudioFileId),
    INDEX IX_Bpm (Bpm),
    INDEX IX_MusicalKey (MusicalKey)
);

-- Sections (verse, chorus, etc.)
CREATE TABLE Sections (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AnalysisResultId UNIQUEIDENTIFIER NOT NULL,
    StartTime FLOAT NOT NULL,
    EndTime FLOAT NOT NULL,
    Label NVARCHAR(50) NOT NULL,
    FOREIGN KEY (AnalysisResultId) REFERENCES AnalysisResults(Id) ON DELETE CASCADE,
    INDEX IX_AnalysisResultId (AnalysisResultId)
);

-- Chord annotations
CREATE TABLE ChordAnnotations (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AnalysisResultId UNIQUEIDENTIFIER NOT NULL,
    StartTime FLOAT NOT NULL,
    EndTime FLOAT NOT NULL,
    Chord NVARCHAR(20) NOT NULL,
    FOREIGN KEY (AnalysisResultId) REFERENCES AnalysisResults(Id) ON DELETE CASCADE,
    INDEX IX_AnalysisResultId (AnalysisResultId)
);

-- Generation requests
CREATE TABLE GenerationRequests (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    TargetStems NVARCHAR(500) NOT NULL, -- JSON array of stem types
    Parameters NVARCHAR(MAX) NOT NULL, -- JSON parameters
    Status NVARCHAR(20) NOT NULL,
    RequestedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CompletedAt DATETIME2 NULL,
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_AudioFileId (AudioFileId),
    INDEX IX_Status (Status)
);

-- Generated stems
CREATE TABLE GeneratedStems (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    GenerationRequestId UNIQUEIDENTIFIER NOT NULL,
    StemType NVARCHAR(20) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    DurationSeconds FLOAT NOT NULL,
    GeneratedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    FOREIGN KEY (GenerationRequestId) REFERENCES GenerationRequests(Id) ON DELETE CASCADE,
    INDEX IX_GenerationRequestId (GenerationRequestId)
);

-- Job tracking for Durable Functions
CREATE TABLE Jobs (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    JobType NVARCHAR(50) NOT NULL, -- Analysis, Generation
    EntityId UNIQUEIDENTIFIER NOT NULL, -- AudioFileId or GenerationRequestId
    OrchestrationInstanceId NVARCHAR(100) NOT NULL,
    Status NVARCHAR(20) NOT NULL,
    StartedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CompletedAt DATETIME2 NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    INDEX IX_OrchestrationInstanceId (OrchestrationInstanceId),
    INDEX IX_Status (Status)
);
```

---

## 🐳 Containerization Strategy

### Analysis Worker Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements-analysis.txt .
RUN pip install --no-cache-dir -r requirements-analysis.txt

# Install analysis libraries
RUN pip install demucs essentia-tensorflow madmom librosa chord-extractor

WORKDIR /app
COPY analysis_worker/ .

# Expose worker port
EXPOSE 8080

CMD ["python", "worker.py"]
```

### Generation Worker Dockerfile (GPU)

```dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y python3.11 python3-pip ffmpeg
    
# Install PyTorch with CUDA support
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install generation models
COPY requirements-generation.txt .
RUN pip3 install --no-cache-dir -r requirements-generation.txt

# Install model libraries
RUN pip3 install audiocraft stable-audio-tools diffsinger

WORKDIR /app
COPY generation_worker/ .

EXPOSE 8080

CMD ["python3", "worker.py"]
```

---

## 🚀 Azure Infrastructure (Bicep)

### Key Azure Resources

```bicep
// Main resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-music-platform-prod'
  location: 'eastus'
}

// Azure Kubernetes Service
resource aks 'Microsoft.ContainerService/managedClusters@2023-10-01' = {
  name: 'aks-music-workers'
  location: rg.location
  properties: {
    kubernetesVersion: '1.28'
    dnsPrefix: 'music-platform'
    agentPoolProfiles: [
      {
        name: 'cpupool'
        count: 3
        vmSize: 'Standard_D8s_v3'
        mode: 'System'
      }
      {
        name: 'gpupool'
        count: 2
        vmSize: 'Standard_NC6s_v3' // NVIDIA Tesla V100
        mode: 'User'
        nodeTaints: ['gpu=true:NoSchedule']
      }
    ]
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Azure Storage Account
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stmusicaudio'
  location: rg.location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// Blob containers
resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource rawAudioContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobServices
  name: 'raw-audio'
}

resource stemsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobServices
  name: 'stems'
}

// Azure SQL Database
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: 'sql-music-metadata'
  location: rg.location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: '<use-key-vault>'
    version: '12.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: 'music-metadata'
  location: rg.location
  sku: {
    name: 'S3'
    tier: 'Standard'
  }
}

// Azure OpenAI
resource openai 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: 'openai-music-orchestration'
  location: 'eastus'
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'music-orchestration'
  }
}

// Azure Functions (Durable Functions)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'plan-durable-functions'
  location: rg.location
  sku: {
    name: 'EP1'
    tier: 'ElasticPremium'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'func-music-orchestrator'
  location: rg.location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOTNET-ISOLATED|8.0'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};...'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
      ]
    }
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-music-platform'
  location: rg.location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}
```

---

## 🔐 Security & Authentication

### 1. Authentication Strategy
- **API Authentication**: Azure AD B2C or Azure AD with OAuth2/OIDC
- **Service-to-Service**: Managed Identity for all Azure services
- **Storage Access**: SAS tokens with time-limited expiration
- **Database**: Azure SQL with Azure AD authentication

### 2. Network Security
- **AKS Network Policies**: Restrict pod-to-pod communication
- **Azure Private Link**: Private connectivity to storage and SQL
- **Application Gateway**: WAF protection for API endpoints
- **Key Vault**: All secrets stored in Azure Key Vault

### 3. RBAC Roles
```csharp
// Custom RBAC implementation
public enum MusicPlatformRole
{
    Admin,          // Full access
    Analyst,        // Can analyze audio
    Generator,      // Can generate stems
    Viewer          // Read-only access
}
```

---

## 📊 Monitoring & Observability

### Application Insights Integration

```csharp
public class TelemetryService
{
    private readonly TelemetryClient _telemetryClient;
    
    public void TrackAnalysisStarted(Guid audioFileId)
    {
        _telemetryClient.TrackEvent("AnalysisStarted", 
            new Dictionary<string, string>
            {
                ["AudioFileId"] = audioFileId.ToString()
            });
    }
    
    public void TrackGenerationMetrics(GenerationResult result)
    {
        _telemetryClient.TrackMetric("GenerationDuration", 
            result.DurationSeconds);
        _telemetryClient.TrackMetric("StemsGenerated", 
            result.Stems.Count);
    }
}
```

### Key Metrics to Track
- Audio processing time (P50, P95, P99)
- Model inference latency
- Blob storage throughput
- Database query performance
- Durable Functions execution time
- GPU utilization (AKS nodes)
- Queue depth (Service Bus)

---

## 🧪 Testing Strategy

### Unit Tests
- Domain model validation
- Service layer logic
- Repository patterns

### Integration Tests
- API endpoint testing
- Database operations
- Blob storage operations
- Durable Functions orchestration (in-process)

### End-to-End Tests
- Full pipeline: Upload → Analysis → Generation
- Load testing with concurrent requests
- GPU worker stress testing

---

## 📦 Deployment Strategy

### CI/CD Pipeline (Azure DevOps / GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy Music Platform

on:
  push:
    branches: [main]

jobs:
  build-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build .NET API
        run: dotnet build src/MusicPlatform.Api
      - name: Run tests
        run: dotnet test tests/
      - name: Publish
        run: dotnet publish -c Release
        
  build-workers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Analysis Worker Image
        run: docker build -t music-analysis-worker:${{ github.sha }} workers/analysis
      - name: Build Generation Worker Image
        run: docker build -t music-generation-worker:${{ github.sha }} workers/generation
      - name: Push to ACR
        run: |
          az acr login --name musicplatformacr
          docker push music-analysis-worker:${{ github.sha }}
          docker push music-generation-worker:${{ github.sha }}
          
  deploy-infrastructure:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy Bicep
        run: az deployment group create --resource-group rg-music-platform --template-file infrastructure/main.bicep
```

---

## 💰 Cost Estimation (Monthly)

| Service | Configuration | Est. Cost (USD) |
|---------|--------------|-----------------|
| AKS (CPU pool) | 3x Standard_D8s_v3 | ~$730 |
| AKS (GPU pool) | 2x Standard_NC6s_v3 | ~$2,190 |
| Azure SQL Database | S3 (100 DTU) | ~$200 |
| Blob Storage | 1TB Hot tier | ~$20 |
| Azure Functions | Premium EP1 | ~$160 |
| Azure OpenAI | GPT-4 (100K tokens/day) | ~$300 |
| Application Insights | 10GB/month | ~$25 |
| **Total** | | **~$3,625/month** |

---

## 🎯 Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
- [ ] Set up Azure infrastructure (Bicep)
- [ ] Create .NET Core API project
- [ ] Implement database schema and EF Core models
- [ ] Set up Blob Storage integration
- [ ] Create basic API endpoints (upload, query)

### Phase 2: Analysis Pipeline (Weeks 5-8)
- [ ] Implement Durable Functions orchestrator
- [ ] Create Analysis Worker (Docker + Python)
- [ ] Integrate Demucs for source separation
- [ ] Integrate Essentia/madmom for MIR
- [ ] Implement JAMS annotation storage

### Phase 3: Generation Pipeline (Weeks 9-12)
- [ ] Create Generation Worker (GPU Docker)
- [ ] Integrate Stable Audio Open
- [ ] Integrate MusicGen
- [ ] Implement conditioning logic
- [ ] Add LLM orchestration (Azure OpenAI)

### Phase 4: UI & Polish (Weeks 13-16)
- [ ] Build React/Blazor web UI
- [ ] Add audio player for stem audition
- [ ] Implement generation approval workflow
- [ ] Add monitoring dashboards
- [ ] Performance optimization
- [ ] Documentation and deployment guides

---

## 🤝 Team Roles & Responsibilities

### Lead .NET/Azure Engineer
- Azure architecture and Bicep templates
- Durable Functions orchestration
- API design and implementation
- CI/CD pipeline setup

### Audio ML Engineer
- Source separation (Demucs)
- Music generation models (Stable Audio, MusicGen)
- Model optimization and quantization
- GPU inference optimization

### MIR Specialist
- Chord/key detection algorithms
- Beat tracking and tempo estimation
- Structure segmentation
- JAMS schema implementation

### DevOps Engineer
- AKS cluster management
- GPU node pool configuration
- Monitoring and alerting
- Security hardening

### Full-Stack Developer
- React/Blazor UI
- API integration
- Audio player implementation
- User experience design

---

## 📚 References

### Azure Documentation
- [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview)
- [Azure Kubernetes Service](https://learn.microsoft.com/en-us/azure/aks/)
- [Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

### Music Processing Libraries
- [Demucs](https://github.com/facebookresearch/demucs) - Source separation
- [Essentia](https://essentia.upf.edu/) - MIR algorithms
- [madmom](https://madmom.readthedocs.io/) - Beat tracking
- [JAMS](https://jams.readthedocs.io/) - Annotation format

### AI Generation Models
- [Stable Audio Open](https://github.com/Stability-AI/stable-audio-tools)
- [MusicGen](https://github.com/facebookresearch/audiocraft)
- [DiffSinger](https://github.com/MoonInTheRiver/DiffSinger)

---

## ✅ Success Criteria

1. **Functionality**
   - End-to-end pipeline processes MP3 → analysis → metadata → generation
   - JAMS-compliant annotation storage
   - Realistic stem generation with proper conditioning

2. **Performance**
   - Analysis completes within 5 minutes for 3-minute song
   - Generation completes within 10 minutes per stem
   - API response time < 200ms (p95)

3. **Scalability**
   - Handle 100 concurrent analysis jobs
   - Automatically scale AKS nodes based on queue depth
   - Process 1000+ songs per day

4. **Reliability**
   - 99.9% uptime for API
   - Automatic retry for failed jobs
   - Graceful degradation on GPU unavailability

5. **Security**
   - Zero hardcoded credentials
   - All secrets in Key Vault
   - Network isolation for worker nodes
   - RBAC enforced at all layers

---

**Document Version:** 1.0  
**Last Updated:** October 13, 2025  
**Status:** Ready for Implementation
