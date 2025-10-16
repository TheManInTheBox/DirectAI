# 🎵 AI-Powered Music Analysis & Generation Platform
## Expert Team Recruitment - Production Azure/.NET Project

---

## 📋 Project Overview

**Project Title:** AI-Powered Music Analysis & Generation Platform (.NET + Azure)

**Objective:** Build a production-grade system that ingests MP3 files, analyzes musical structure (sections, chords, key, tempo, tuning), stores metadata in a queryable format, and generates new stems/loops (guitar, bass, drums, vocals) using state-of-the-art AI models. The entire system must be **scalable, secure, observable, and Azure-native**.

**Technology Stack:**
- **.NET 8.0** (Web API, Durable Functions, Background Workers)
- **Azure Cloud** (AKS, Durable Functions, Blob Storage, SQL Database, OpenAI)
- **Python ML** (Demucs, Essentia, madmom, PyTorch-based audio generation models)
- **Containers & Orchestration** (Docker, Kubernetes, GPU workloads)

**Budget:** ~$150K - $250K (depending on timeline and team size)  
**Timeline:** 12-16 weeks for MVP, 6+ months for production-ready platform  
**Location:** Remote-first (US/EU timezones preferred)

---

## 🎯 Core Responsibilities

### 1️⃣ Audio Analysis Pipeline
- Implement **source separation** using Demucs (vocals, drums, bass, other)
- Extract **Music Information Retrieval (MIR)** features:
  - Beats, tempo, time signatures
  - Key, mode, chord progressions
  - Tuning analysis (Hz deviation from A440)
  - Structural segmentation (verse, chorus, bridge)
- Store annotations in **JAMS format** (JSON Annotated Music Specification)
- Integrate with **Essentia, madmom, librosa, chord-extractor**

### 2️⃣ AI Generation Layer
- Integrate open-source generative models:
  - **Stable Audio Open** (stem generation)
  - **MusicGen** (melody/accompaniment)
  - **DiffSinger** (vocal synthesis)
- Design **conditioning logic** for realistic outputs:
  - BPM, chord grid, section labels
  - Style transfer (e.g., "convert to jazz piano")
- Optimize inference for **GPU workloads** (NVIDIA T4/A10/A100)

### 3️⃣ Orchestration & Infrastructure
- Architect **Azure Durable Functions** for stateful multi-step workflows
- Deploy containerized workers on **Azure Kubernetes Service (AKS)**:
  - **CPU pods** for DSP/MIR (analysis workers)
  - **GPU pods** for ML inference (generation workers)
- Use **Azure Blob Storage** for audio assets (hot/cool tiers)
- Use **Azure SQL Database** or **PostgreSQL** for metadata

### 4️⃣ LLM Integration
- Develop **Azure OpenAI** integration for:
  - Pipeline planning ("which models to use for this request?")
  - Prompt generation for generation models
  - Natural language query interface (future feature)
- Ensure LLM **coordinates** tasks, not performs raw DSP

### 5️⃣ API & UI
- Build **.NET Core Web API** for:
  - Audio ingestion (MP3 upload)
  - Metadata query (SQL queries + JAMS annotations)
  - Generation requests (async job submission)
  - Health checks and monitoring endpoints
- Provide **minimal web UI** for:
  - Uploading audio files
  - Viewing analysis results (chord charts, waveforms)
  - Auditioning generated stems (HTML5 audio player)
  - Approving/rejecting outputs

---

## 🧑‍💼 Ideal Team Composition

### **Lead .NET/Azure Engineer** (1 position)
**Responsibilities:**
- Design overall Azure architecture (Bicep/Terraform)
- Implement Durable Functions orchestration
- Build .NET Core Web API with Entity Framework Core
- Set up CI/CD pipelines (GitHub Actions / Azure DevOps)
- Manage Azure resources (AKS, Storage, SQL, Functions)

**Required Skills:**
- 5+ years .NET experience (C# 11+, .NET 8.0)
- 3+ years Azure cloud architecture
- Deep understanding of Durable Functions, Service Bus, Event Grid
- Experience with AKS and containerized .NET apps
- Strong knowledge of Azure security (Managed Identity, Key Vault, RBAC)

**Nice to Have:**
- Azure certifications (AZ-204, AZ-305)
- Experience with Bicep or Terraform
- Background in media/audio processing systems

**Rate:** $120 - $180/hour (USD)

---

### **Audio ML Engineer** (1 position)
**Responsibilities:**
- Implement source separation (Demucs fine-tuning if needed)
- Integrate generative models (Stable Audio, MusicGen, DiffSinger)
- Optimize PyTorch models for inference (quantization, ONNX export)
- Design conditioning pipelines for generation
- GPU profiling and optimization

**Required Skills:**
- 3+ years ML engineering (PyTorch, HuggingFace, librosa)
- Experience with audio/music generation models
- Strong DSP fundamentals (FFT, spectrograms, audio synthesis)
- Proficiency in Python (NumPy, SciPy, torchaudio)
- Understanding of GPU optimization (CUDA, TensorRT)

**Nice to Have:**
- Published research in audio ML (ISMIR, ICASSP, NeurIPS)
- Experience with Demucs, Spleeter, or similar tools
- Knowledge of MIDI, MusicXML, or JAMS formats

**Rate:** $100 - $160/hour (USD)

---

### **MIR Specialist** (1 position)
**Responsibilities:**
- Implement chord detection algorithms (CREMA, Chordino)
- Implement beat tracking and tempo estimation (madmom, Essentia)
- Design structure segmentation (MSAF, Librosa)
- Convert outputs to JAMS format
- Validate analysis quality against ground truth datasets

**Required Skills:**
- 3+ years experience in Music Information Retrieval
- Proficiency with Essentia, madmom, librosa, mir_eval
- Understanding of music theory (chords, keys, harmony)
- Experience with JAMS, mirdata, or similar annotation formats
- Python expertise (pandas, scipy)

**Nice to Have:**
- PhD or Master's in Music Technology/Audio Engineering
- Experience with Spotify API, AcousticBrainz
- Publications in MIR field (ISMIR, ICME)

**Rate:** $90 - $140/hour (USD)

---

### **DevOps Engineer** (1 position)
**Responsibilities:**
- Set up AKS cluster with GPU node pools
- Create Dockerfiles for analysis/generation workers
- Implement Kubernetes manifests (Deployments, Services, HPA)
- Configure CI/CD pipelines (build, test, deploy)
- Set up monitoring (Application Insights, Prometheus, Grafana)

**Required Skills:**
- 3+ years DevOps/SRE experience
- Strong Kubernetes expertise (networking, GPU scheduling)
- Docker containerization best practices
- Azure DevOps or GitHub Actions
- Infrastructure as Code (Bicep, Terraform, Helm)

**Nice to Have:**
- Experience with GPU workloads on Kubernetes (NVIDIA device plugin)
- Azure AKS certifications
- Experience with Karpenter or KEDA for autoscaling

**Rate:** $100 - $150/hour (USD)

---

### **Full-Stack Developer** (1 position)
**Responsibilities:**
- Build React or Blazor web UI
- Integrate with .NET Core Web API
- Implement audio player for stem audition (Wavesurfer.js, Howler.js)
- Create chord chart visualizations (D3.js, Chart.js)
- Implement generation approval workflow

**Required Skills:**
- 3+ years full-stack development
- React (TypeScript) or Blazor (C#)
- RESTful API integration
- Experience with audio/video players in browser
- Responsive UI design (Tailwind, MUI, Bootstrap)

**Nice to Have:**
- Experience with music/audio applications
- Knowledge of Web Audio API
- Background in UI/UX design

**Rate:** $80 - $130/hour (USD)

---

## 📦 Deliverables

### Phase 1: Foundation (Weeks 1-4)
- [ ] Azure infrastructure deployed (AKS, Storage, SQL, Functions)
- [ ] .NET Core API with authentication and authorization
- [ ] Database schema and Entity Framework migrations
- [ ] CI/CD pipeline for automated deployments

### Phase 2: Analysis Pipeline (Weeks 5-8)
- [ ] Durable Functions orchestrator for analysis workflow
- [ ] Dockerized analysis worker (Demucs, Essentia, madmom)
- [ ] JAMS annotation storage and query API
- [ ] End-to-end analysis pipeline (MP3 → metadata → database)

### Phase 3: Generation Pipeline (Weeks 9-12)
- [ ] Dockerized generation worker (Stable Audio, MusicGen)
- [ ] LLM orchestration for pipeline planning
- [ ] Conditioning logic (BPM, chords, structure)
- [ ] Generation API endpoints (request, poll status, download)

### Phase 4: UI & Polish (Weeks 13-16)
- [ ] Web UI for audio upload and metadata viewing
- [ ] Stem audition player with waveform visualization
- [ ] Generation request form and approval workflow
- [ ] Monitoring dashboards (Application Insights)
- [ ] Documentation and deployment guides

---

## 🔧 Required Expertise Summary

| Skill Area | Priority | Technologies |
|-----------|----------|--------------|
| **.NET Core & Azure** | **Critical** | C#, ASP.NET Core, Durable Functions, AKS, Blob, SQL, Service Bus |
| **Audio DSP & MIR** | **Critical** | Essentia, madmom, librosa, Demucs, chord-extractor, JAMS |
| **ML for Audio** | **Critical** | PyTorch, HuggingFace, Stable Audio, MusicGen, DiffSinger |
| **LLM Orchestration** | High | Azure OpenAI, prompt engineering, function calling |
| **Data Modeling** | High | SQL, Entity Framework Core, JSON schemas, JAMS |
| **DevOps** | High | Docker, Kubernetes, GPU scheduling, CI/CD, monitoring |
| **Full-Stack UI** | Medium | React/Blazor, TypeScript, Web Audio API |

---

## ✅ Selection Criteria

### Must Have:
✅ **Production experience** (not just research prototypes)  
✅ **Azure cloud deployment** experience (or equivalent AWS/GCP)  
✅ **Strong communication skills** (remote-first team)  
✅ **Portfolio links** for audio ML or Azure projects  
✅ **Availability** for 12-16 week engagement (part-time OK)

### Strong Preference:
⭐ Published research or open-source contributions in audio ML  
⭐ Experience with music industry tools (DAWs, VST plugins)  
⭐ Background in live music production or audio engineering  
⭐ Prior work with GPU-accelerated inference at scale

---

## 📧 How to Apply

**Email:** [your-email@domain.com]  
**Subject:** `Music Platform Expert - [Your Role]`

**Include:**
1. **Resume/CV** (PDF)
2. **Portfolio Links:**
   - GitHub repositories (audio ML projects)
   - Azure deployments (architecture diagrams)
   - Music/audio applications you've built
3. **Cover Letter** (2-3 paragraphs):
   - Why you're excited about this project
   - Relevant experience with audio ML or Azure
   - Availability and hourly rate
4. **Code Sample** (optional but highly valued):
   - Link to a music analysis script or audio generation notebook

---

## 🚀 Why Join This Project?

✨ **Cutting-edge tech:** Work with the latest AI models (Stable Audio, MusicGen)  
✨ **Production impact:** Build a real product used by musicians and producers  
✨ **Azure best practices:** Enterprise-grade architecture with observability  
✨ **Creative domain:** Music and AI—combine technical depth with artistic output  
✨ **Remote flexibility:** Work from anywhere, async collaboration  
✨ **Strong compensation:** Competitive rates for specialized expertise

---

## 📚 References & Resources

### Architecture Documentation
- [Full Architecture Spec](./docs/MUSIC_PLATFORM_ARCHITECTURE.md)
- [Domain Models](./src/MusicPlatform.Domain/Models/)
- [Database Schema](./database/schema.sql)

### Azure Documentation
- [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview)
- [Azure Kubernetes Service](https://learn.microsoft.com/en-us/azure/aks/)
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

**Project Status:** 🟢 Actively Hiring  
**Last Updated:** October 13, 2025  
**Expected Start Date:** November 2025

---

*We're building something truly innovative at the intersection of AI and music. If you're passionate about audio technology and want to work on a real production system (not a research toy), we'd love to hear from you!*

**Apply today and let's create the future of AI-powered music production together.** 🎸🎹🥁🎤
