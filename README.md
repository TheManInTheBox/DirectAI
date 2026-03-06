# DirectAI

**AI Inference Inside Your Azure.** Production-grade, multi-modal inference deployed inside your own Azure subscription. Data never leaves your boundary.

Drop-in OpenAI-compatible API for LLMs, embeddings, and speech-to-text — backed by vLLM, TensorRT-LLM, and ONNX Runtime on AKS GPU clusters. Purpose-built for healthcare, financial services, and government organizations where compliance requirements (HIPAA, SOC 2, data residency) disqualify third-party inference APIs.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Why DirectAI?

| | Third-Party API (Baseten, Together, etc.) | Self-Managed vLLM on AKS | **DirectAI** |
|---|---|---|---|
| **Data residency** | ❌ Data leaves your boundary | ✅ Your subscription | ✅ Your subscription |
| **Compliance** | ❌ Shared infra | ✅ Full control | ✅ Full control + docs |
| **Time to production** | Days | 3–6 months | **Hours** |
| **OpenAI-compatible** | Varies | DIY | ✅ Drop-in |
| **Autoscaling / zero-cost idle** | ✅ | DIY | ✅ Built-in |
| **Vendor lock-in** | High | None | **None — Apache 2.0** |

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │      Customer's Azure Subscription      │
                         │           AKS GPU Cluster               │
                         │                                         │
  Client ──► Ingress ──► │  API Server (FastAPI routing proxy)     │
  (OpenAI SDK)           │    │                                    │
                         │    ├──► vLLM Engine (T4/A100/H100)     │
                         │    │     └─ /v1/chat/completions        │
                         │    │                                    │
                         │    ├──► TRT-LLM Engine  (A100/H100)    │
                         │    │     └─ /v1/chat/completions        │
                         │    │     └─ /v1/audio/transcriptions    │
                         │    │                                    │
                         │    └──► Embeddings Engine (T4/A10G)     │
                         │          └─ /v1/embeddings              │
                         │                                         │
                         │  KEDA ──► Pod autoscaling               │
                         │  Cluster Autoscaler ──► Node scaling    │
                         └─────────────────────────────────────────┘
```

The **API server** does NOT run inference — it resolves model names, validates requests, and proxies traffic to the correct GPU backend via httpx HTTP/2.

## Endpoints

### OpenAI-Compatible

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | Chat completions (streaming SSE + sync) |
| `POST` | `/v1/embeddings` | Text embeddings |
| `POST` | `/v1/audio/transcriptions` | Audio transcription (multipart) |
| `GET` | `/v1/models` | List all registered models |

### DirectAI Native

| Method | Path | Description |
|--------|------|-------------|
| `POST/GET` | `/api/v1/models` | Model lifecycle CRUD |
| `POST/GET` | `/api/v1/deployments` | Deployment management |
| `GET` | `/api/v1/engine-cache` | Compiled engine registry |
| `GET` | `/api/v1/system/health` | Service health snapshot |
| `GET` | `/api/v1/system/capacity` | GPU pool capacity and utilization |

### Health & Observability

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe |
| `GET` | `/metrics` | Prometheus metrics |

## Repository Structure

```
DirectAI/
├── .github/workflows/           # CI/CD pipelines (9 workflows)
│   ├── onboard-customer.yml     # Automated customer onboarding
│   ├── deploy-platform.yml      # Shared platform infra
│   ├── deploy-stamp.yml         # Regional stamp deployment
│   ├── build-api-server.yml     # API server CI/CD
│   ├── build-web.yml            # Web app CI/CD
│   ├── build-engines.yml        # Inference engine images
│   ├── compile-engine.yml       # TRT-LLM engine compilation
│   ├── deploy-model.yml         # Model deployment
│   └── populate-cache.yml       # Pre-compile engine cache
├── infra/                       # Bicep IaC (Azure Verified Modules)
│   ├── main.bicep               # Stamp orchestrator
│   ├── platform/main.bicep      # Shared platform infra
│   ├── customers/               # Customer manifests
│   └── environments/            # Per-env parameter files
├── src/
│   ├── api-server/              # FastAPI routing proxy (Python 3.11)
│   ├── embeddings-engine/       # ONNX Runtime GPU embedding server
│   ├── trtllm-engine/           # TensorRT-LLM chat/STT server
│   └── web/                     # Next.js marketing + dashboard
└── deploy/
    ├── models/                  # ModelDeployment YAML configs
    └── helm/directai/           # Helm chart (24 templates)
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

Or use Docker Compose (starts API server + Ollama):

```bash
docker compose up                          # Core: API server + Ollama
docker compose --profile embeddings up     # + ONNX embeddings engine (CPU)
docker compose --profile web up            # + Next.js web app
docker compose --profile all up            # Everything
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
# API server (unit + integration — 216 tests)
cd src/api-server && python -m pytest tests/ -v

# TRT-LLM engine (runs in stub mode — no GPU needed)
cd src/trtllm-engine && pip install -e ".[dev]" && python -m pytest tests/ -v

# Embeddings engine
cd src/embeddings-engine && pip install -e ".[dev,cpu]" && python -m pytest tests/ -v
```

## Inference Engines

| Engine | Modality | When to Use |
|--------|----------|-------------|
| **vLLM** | LLMs | Default for dev/staging. No build step — point at HuggingFace model and go. |
| **TensorRT-LLM** | LLMs, STT | Production A100/H100 where compilation ROI justifies 30–60 min build time. |
| **ONNX Runtime** | Embeddings, reranking | Dynamic batching, async queue, GPU-accelerated. |
| **Ollama** | LLMs (local dev) | Local development only — zero setup. |

All engines expose OpenAI-compatible HTTP APIs on port 8001 and run inside GPU containers on AKS.

## Deployment

### Infrastructure (Bicep)

Each customer gets an **isolated Azure subscription** with a regional "stamp":

```bash
# Deploy a stamp (validate → what-if → approval gate → deploy)
# Run via GitHub Actions: deploy-stamp.yml
```

**Resources per stamp:** AKS (GPU node pools), Storage Account (model weights), Key Vault, Log Analytics, VNet, ACR (optional), 2 Managed Identities (control plane + kubelet, least-privilege).

### Application (Helm)

```bash
helm upgrade --install directai deploy/helm/directai \
  --namespace directai --create-namespace \
  -f deploy/helm/directai/values-dev.yaml \
  --set apiServer.image.tag=<sha>
```

### Adding a New Customer

Run the `Onboard Customer` workflow from GitHub Actions. It creates the subscription, identity, RBAC, GitHub environments, and commits manifest/parameter files — zero manual steps.

## Configuration

All API server settings use the `DIRECTAI_` prefix. Copy `.env.example` to `.env` for local dev:

| Variable | Default | Description |
|----------|---------|-------------|
| `DIRECTAI_PORT` | `8000` | Bind port |
| `DIRECTAI_LOG_LEVEL` | `info` | Log level |
| `DIRECTAI_MODEL_CONFIG_DIR` | `/app/models` | Model YAML directory |
| `DIRECTAI_API_KEYS` | *(empty)* | Comma-separated API keys (empty = auth disabled) |
| `DIRECTAI_BACKEND_TIMEOUT` | `300` | Backend request timeout (seconds) |
| `DIRECTAI_RATE_LIMIT_RPM` | `60` | Per-key rate limit (requests/minute) |
| `DIRECTAI_DATABASE_URL` | *(empty)* | PostgreSQL connection for key validation + billing |
| `DIRECTAI_OTEL_ENABLED` | `true` | Enable OpenTelemetry tracing |

See `.env.example` for the full list.

## Pricing

4 tiers — hybrid billing (base fee + metered per-token usage).

| | Free | Pro ($50/mo + usage) | Managed ($3,500/mo + usage) | Enterprise (Custom) |
|---|---|---|---|---|
| **Base** | $0/mo (self-hosted) or $5 one-time credit (shared API) | $50/mo + per-token usage | $3,500/mo + per-token usage | Custom flat fee (starting $10K/mo) |
| **Compute** | Customer pays Azure directly (self-hosted) | Included in per-token rates | Included in per-token rates | Customer pays Azure directly |
| **Deployment** | Self-service (Helm + Bicep) | Shared DirectAI cluster | Isolated DirectAI-owned subscription | Customer's own subscription |
| **Models** | Any OSS model | Curated (Qwen, Llama, BGE, Whisper) | Any OSS + fine-tuned | + custom model optimization |
| **Rate limits** | 20 RPM / 40K TPM | 300 RPM / 500K TPM | 1,000 RPM / 5M TPM | Custom |
| **Support** | Community (GitHub Issues) | Email, 48hr SLA | Email, 24hr SLA | Slack + phone, 1hr SLA |
| **SLA** | Best-effort | 99.5% | 99.9% | 99.99% |
| **Lock-in** | None — Apache 2.0 | None | None | None |

### Per-Token Usage Rates

| Modality | Metric | Pro | Managed (2×) |
|---|---|---|---|
| Chat — input | per 1M tokens | $1.00 | $2.00 |
| Chat — output | per 1M tokens | $2.00 | $4.00 |
| Embeddings | per 1M tokens | $0.10 | $0.20 |
| Transcription | per minute | $0.10 | $0.20 |

Free/Pro targets developers and startups. Managed targets teams needing isolated infrastructure without managing it. Enterprise targets regulated enterprises (healthcare, financial services, government) where data must stay in the customer's own Azure subscription.

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

Copyright 2025-2026 DirectAI Contributors.
