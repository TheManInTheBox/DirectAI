# DirectAI

High-performance, multi-modal AI inference API on Azure. Drop-in OpenAI-compatible replacement for LLMs, embeddings, and speech-to-text — backed by TensorRT-LLM and ONNX Runtime on AKS GPU clusters.

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │           Azure AKS Cluster             │
                         │                                         │
  Client ──► Ingress ──► │  API Server (FastAPI routing proxy)     │
  (OpenAI SDK)           │    │                                    │
                         │    ├──► TRT-LLM Engine  (A100/H100)    │
                         │    │     └─ /v1/chat/completions        │
                         │    │     └─ /v1/audio/transcriptions    │
                         │    │                                    │
                         │    └──► Embeddings Engine (A10G)        │
                         │          └─ /v1/embeddings              │
                         │                                         │
                         │  KEDA ──► Pod autoscaling               │
                         │  Cluster Autoscaler ──► Node scaling    │
                         └─────────────────────────────────────────┘
```

The **API server** does NOT run inference — it resolves model names, validates requests, and proxies traffic to the correct GPU backend via httpx HTTP/2.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | Chat completions (streaming SSE + sync) |
| `POST` | `/v1/embeddings` | Text embeddings |
| `POST` | `/v1/audio/transcriptions` | Audio transcription (multipart) |
| `GET` | `/v1/models` | List all registered models |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe |
| `GET` | `/metrics` | Prometheus metrics |

## Repository Structure

```
DirectAI/
├── .github/workflows/           # CI/CD pipelines
│   ├── build-api-server.yml     # Lint → test → build → optional deploy
│   ├── build-engines.yml        # Lint → test → build engine images
│   ├── deploy-stamp.yml         # Bicep IaC deployment per region
│   └── onboard-customer.yml     # Automated customer provisioning
├── infra/                       # Bicep IaC (AKS, Storage, ACR, KeyVault, VNet)
│   ├── main.bicep               # Stamp orchestrator
│   ├── customers/               # Customer manifests
│   └── environments/            # Per-env parameter files
├── src/
│   ├── api-server/              # FastAPI routing proxy
│   ├── embeddings-engine/       # ONNX Runtime GPU embedding server
│   └── trtllm-engine/           # TensorRT-LLM chat/STT server
└── deploy/
    ├── models/                  # ModelDeployment YAML configs
    └── helm/directai/           # Helm chart for K8s deployment
```

## Quick Start (Local Dev)

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) running locally (provides stub LLM/embedding backends)

### 1. Pull models in Ollama

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 2. Start the API server

```bash
cd src/api-server
pip install -e ".[dev]"
DIRECTAI_MODEL_CONFIG_DIR=../../deploy/models/local python -m uvicorn app.main:app --reload --port 8000
```

### 3. Send a request

```bash
# Chat completion
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:3b", "messages": [{"role": "user", "content": "Hello!"}]}'

# Embeddings
curl http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "nomic-embed-text", "input": "Hello world"}'

# List models
curl http://localhost:8000/v1/models
```

## Running Tests

```bash
# API server (unit + integration)
cd src/api-server && python -m pytest tests/ -v

# TRT-LLM engine (runs in stub mode — no GPU needed)
cd src/trtllm-engine && pip install -e ".[dev]" && python -m pytest tests/ -v

# Embeddings engine
cd src/embeddings-engine && pip install -e ".[dev,cpu]" && python -m pytest tests/ -v
```

## Inference Engines

| Engine | Modality | Stack |
|--------|----------|-------|
| **TensorRT-LLM** | LLMs, STT | TRT-LLM HLAPI, version negotiation (0.12+/0.14+/0.16+), stub mode for dev |
| **ONNX Runtime** | Embeddings, reranking | ONNX Runtime GPU, dynamic batching, HuggingFace tokenizers |

Both engines expose OpenAI-compatible HTTP APIs on port 8001 and run inside GPU containers on AKS.

## Deployment

### Infrastructure (Bicep)

Each customer gets an isolated Azure subscription with a regional "stamp":

```bash
# Deploy a stamp (validate → what-if → deploy)
# Run via GitHub Actions: deploy-stamp.yml
```

**Resources per stamp:** AKS, Storage Account, Key Vault, Log Analytics, VNet, ACR (optional), 2 Managed Identities.

### Application (Helm)

```bash
helm upgrade --install directai deploy/helm/directai \
  --namespace directai --create-namespace \
  --set apiServer.image.tag=<sha> \
  --set-file "modelConfigs.llama\.yaml=deploy/models/llama-3.1-70b-instruct.yaml"
```

### Adding a New Customer

Run the `Onboard Customer` workflow from GitHub Actions. It creates the subscription, identity, RBAC, GitHub environments, and commits manifest/parameter files — zero manual steps.

## Configuration

All API server settings use the `DIRECTAI_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `DIRECTAI_PORT` | `8000` | Bind port |
| `DIRECTAI_LOG_LEVEL` | `info` | Log level |
| `DIRECTAI_MODEL_CONFIG_DIR` | `/app/models` | Model YAML directory |
| `DIRECTAI_API_KEYS` | *(empty)* | Comma-separated API keys (empty = auth disabled) |
| `DIRECTAI_BACKEND_TIMEOUT` | `300` | Backend request timeout (seconds) |

## License

Proprietary. All rights reserved.
