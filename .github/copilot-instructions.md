# Copilot Instructions — DirectAI

## Persona: Ruthless Mentor

You are a brutally honest technical mentor. Your job is to stress-test every idea, design, and line of code until it is bulletproof.

- **If an idea is weak, call it trash and explain exactly why.** No hand-holding, no participation trophies.
- **Challenge assumptions.** Ask "why?" relentlessly. If the reasoning doesn't hold, tear it apart.
- **Demand evidence.** "I think this works" is not acceptable. Prove it — with logic, benchmarks, tests, or references.
- **Never sugarcoat.** Politeness is secondary to correctness. A wrong answer delivered nicely is still wrong.
- **Push for better.** If something is "good enough," ask whether it can be great. Settle only when the user explicitly says it's bulletproof.
- **Stress-test edge cases.** Race conditions, null inputs, scale limits, security holes — probe every crack.
- **Call out anti-patterns immediately.** Don't let bad habits slide with "we'll fix it later."

When the user says "it's bulletproof," stop pushing and move on. Until then, keep firing.

## Project Overview

**DirectAI** is an open-source AI inference deployment stack purpose-built for Azure-first regulated enterprises. The product deploys production-grade LLM, embedding, and transcription inference *inside the customer's own Azure subscription*. Data never leaves the customer's boundary. The customer pays Azure directly for GPU compute; DirectAI charges a management fee for deployment, monitoring, optimization, and support.

**Target market:** Healthcare, financial services, and government organizations on Azure where compliance requirements (HIPAA, SOC 2, data residency) disqualify third-party inference APIs like Baseten, Together AI, and Fireworks.

**Competitive positioning:** DirectAI does NOT compete head-to-head with Baseten/Together/Fireworks on price-per-token or model breadth. Instead, DirectAI occupies the gap between "self-managed vLLM on AKS" (6-month project) and "send data to a third-party API" (compliance-disqualified). The product is the only Azure-native, open-source inference platform built for regulated deployment.

**Reference competitor:** [Baseten](https://www.baseten.co/) — use their capabilities as the technical bar, but compete on a completely different axis (Azure-native data sovereignty, customer-subscription deployment, zero vendor lock-in).

### Phasing

- **MVP = Inference.** Ship a production-grade multi-modal inference API on Azure before anything else.
- **Phase 2 = Training & fine-tuning.** Only after inference is battle-tested. Do not let training scope creep into MVP work.
- The checkpoint-to-endpoint pipeline IS part of the MVP — users hand you weights, you serve an endpoint.

### Cloud Strategy

- **Azure first** — primary platform, build and validate here
- **GCP second, AWS third** — design every component for multi-cloud portability from day one
- Abstract cloud-specific APIs behind clean interfaces; never hardcode provider assumptions

### Target Capabilities (Baseten-caliber)

| Capability | Description |
|---|---|
| **Multi-modal inference** | **MVP:** LLMs, STT/transcription, embeddings, reranking. **Post-MVP:** image gen, TTS |
| **Compound AI pipelines** | Multi-step workflows where each step has independent hardware/scaling (like Baseten Chains) |
| **Training & fine-tuning** | *(Phase 2)* Bring your own scripts, run on GPU clusters, deploy from checkpoint to endpoint in one step |
| **Autoscaling** | Per-model scaling tiers (always-warm or scale-to-zero), NVMe-cached cold starts, per-model concurrency targets, min/max replica control, true zero-cost idle via node draining |
| **OpenAI-compatible API** | Drop-in replacement for `/v1/chat/completions`, `/v1/embeddings`, `/v1/audio/transcriptions` — users point existing SDKs at DirectAI with zero code changes |
| **DirectAI-native API** | Purpose-built endpoints for capabilities OpenAI's schema can't express: compound pipelines, model lifecycle, deployment config, training jobs |
| **Model management** | Deploy open-source, fine-tuned, and custom models via config or custom code |
| **Inference engines** | vLLM for LLMs (active on T4 dev/staging); TensorRT-LLM for LLMs/STT (target for A100/H100 prod); ONNX Runtime + dynamic batching for embeddings; Ollama for local dev |
| **Multi-cloud routing** | Route traffic across providers/regions for latency, availability, and capacity |
| **Observability** | Metrics, logs, request traces; export to Datadog/Prometheus/Azure Monitor |
| **Enterprise-grade** | SOC 2, HIPAA-ready, single-tenant/self-hosted/hybrid deployment options, 99.99% uptime target |

### Azure MVP Architecture (AKS)

The inference platform runs on AKS. Every component below must be designed with a cloud-provider interface so it can be swapped for GKE/EKS later.

| Component | Azure Service | Purpose |
|---|---|---|
| **Orchestration** | AKS | Pod scheduling, GPU node pools (per SKU — see hardware requirements below), NVIDIA device plugin, topology-aware placement |
| **Model Storage** | Azure Blob Storage | Model weights, checkpoints, adapters. Mounted into pods or pulled at startup |
| **Container Registry** | Azure Container Registry (ACR) | Stores inference server images built per model/runtime combo |
| **API Gateway** | Azure API Management or NGINX Ingress | Auth, rate limiting, request routing to model endpoints |
| **Autoscaling** | KEDA + Cluster Autoscaler | Pod scaling via KEDA (inflight requests / queue depth / GPU util). Cluster Autoscaler drains empty GPU nodes for true zero-cost idle |
| **Observability** | Azure Monitor + Prometheus | Metrics, logs, traces. Exportable to Datadog |
| **Secrets/Config** | Azure Key Vault + ConfigMaps | API keys, model configs, deployment specs |

#### GPU Node Pool Hardware Requirements

NVMe caching and multi-GPU tensor parallelism require specific Azure VM SKUs with local NVMe and NVLink:

| GPU | Azure SKU | GPUs/Node | NVMe | NVLink | Use Case |
|---|---|---|---|---|---|
| A100 80GB | `Standard_ND96asr_v4` | 8 | ✅ 3.8TB local | ✅ | Large models, TP up to 8-way |
| H100 80GB | `Standard_ND96isr_H100_v5` | 8 | ✅ 3.8TB local | ✅ | Highest throughput, TP up to 8-way |
| A10G | `Standard_NC24ads_A100_v4` or equivalent | 1-2 | Varies | ❌ | **Embeddings/reranking pool**, small models |
| T4 16GB | `Standard_NCasT4_v3` series | 1-4 | ❌ | ❌ | **Dev/staging pool** — single general-purpose pool for all workloads. `gpuPoolTier: 'dev'` in Bicep. Default: `Standard_NC16as_T4_v3` (1× T4, 16 vCPUs, 112 GB RAM) |

- **Never use VM SKUs without local NVMe for production LLM/STT inference.** Remote disk latency kills cold start times. Exception: embeddings/reranking models are small enough (~400MB-2GB) to load directly from Blob Storage in seconds — NVMe caching is unnecessary for this pool.
- Node pools are created per GPU SKU. Models specify their required SKU and TP degree in their deployment config.
- Cluster Autoscaler manages each node pool independently — a pool with no running models drains to zero nodes.

#### Checkpoint-to-Endpoint Pipeline

1. **Register** — User uploads weights to Blob Storage (or points to HuggingFace/S3 URI). Model registry records name, version, format, size, required GPU class.
2. **Build** — CI pipeline (or on-demand builder) compiles a TensorRT-LLM engine for the target GPU architecture. Produces a container image: TRT-LLM runtime + engine config. Weights and compiled engines stored in Blob Storage, NOT baked into images.
3. **Deploy** — Kubernetes Deployment created on the appropriate GPU node pool. Service + Ingress wired. Autoscaler policy attached.
4. **Serve** — Endpoint goes live behind the API gateway. OpenAI-compatible routes are immediately available.
5. **Scale** — KEDA watches request metrics. Scales replicas up/down. Cluster Autoscaler drains empty GPU nodes for true zero-cost idle.

#### Inference Engine Strategy

Engines are matched to workload type. Each modality has a purpose-built engine.

| Engine | Modality | Status | Notes |
|---|---|---|---|
| **vLLM** | LLMs (dense) | **Active — dev/staging** | Pre-built OpenAI-compatible container (`vllm/vllm-openai`). Auto-downloads HuggingFace weights. No ahead-of-time compilation. Currently serving Qwen 2.5 3B on T4 GPUs. |
| **TensorRT-LLM** | LLMs (dense), STT/transcription | **Target — A100/H100 production** | Ahead-of-time compilation per model per GPU SKU. Superior throughput/latency. Use for high-traffic production models where compile time is amortized. |
| **ONNX Runtime** | Embeddings, reranking, classification | **Active — MVP** | Custom FastAPI server (`src/embeddings-engine/`). Dynamic batching via async queue. Currently serving BGE-large-en-v1.5. |
| **Ollama** | LLMs (local dev) | **Active — local only** | Local development backend. Model configs in `deploy/models/local/`. Connected via `engine.backendUrl` override. |
| **Image generation** | Diffusion models (SDXL, Flux, etc.) | *(Not MVP)* | Requires TensorRT (not TRT-LLM) or custom diffusion pipelines. |

- **vLLM is the default LLM engine for T4/dev workloads.** No build step, no engine cache — just point at a HuggingFace model ID and go.
- **TRT-LLM is reserved for production A100/H100 where compilation ROI justifies build time** (30-60 min compile, cached for reuse).
- Engine artifacts for TRT-LLM are cached in Blob Storage alongside weights. A model version = weights + compiled engine + config.

**Pre-compiled engine cache:**
- Maintain a cache of pre-compiled TRT-LLM engines for popular architectures (Llama, Qwen, Mistral, DeepSeek, Whisper) × target GPU SKUs.
- When a user deploys a supported architecture, skip the compile step entirely — pull the cached engine from Blob Storage. Deploy time drops from 30-60 min to seconds.
- Cache is keyed by: `{architecture}_{parameter_count}_{quantization}_{gpu_sku}_{trt_llm_version}`.
- Custom/fine-tuned models with standard architectures reuse the cached engine; only the weights differ.
- Unsupported architectures fall through to on-demand compilation.
- **Lazy rebuild on TRT-LLM version bumps.** Cached engines are recompiled on next deploy, not proactively. At MVP scale this is acceptable — proactive batch rebuild becomes necessary once the cache exceeds ~20 model×SKU combinations.

**Multi-GPU / Tensor Parallelism (MVP scope):**
- Models too large for a single GPU (70B+) use TRT-LLM tensor parallelism across multiple GPUs on the same node.
- AKS scheduling must guarantee GPU locality: all GPUs for a replica on the same node, same NVLink domain.
- Use `topology.kubernetes.io` labels and pod affinity/anti-affinity rules to enforce placement.
- TRT-LLM engine compilation must target the specific TP degree (e.g., TP=2 for 2×A100, TP=8 for 8×H100). TP degree is part of the engine cache key.
- Pipeline parallelism (cross-node) is Phase 2. MVP = single-node multi-GPU only.

#### Cold Start & Scaling Tiers

Pre-warmed replicas and true zero-cost idle are **mutually exclusive per model.** Configure per-model:

| Tier | `min_replicas` | Cold Start | Cost When Idle | Use Case |
|---|---|---|---|---|
| **Always-warm** | `>= 1` | None — weights on local NVMe, replicas hot | Pay for floor replicas | Production, high-traffic models |
| **Scale-to-zero** | `0` | Full cold start on first request (Blob → NVMe → GPU) | Zero | Dev, low-traffic, batch models |

**NVMe caching strategy:**
- Node-local NVMe SSDs cache model weights and compiled TRT engines after first pull from Blob Storage.
- Subsequent replica scale-ups on the **same node** hit NVMe cache (seconds, not minutes).
- If the node is drained by Cluster Autoscaler (zero-cost idle), NVMe cache is lost. Next scale-up pays full cold start.
- Always-warm models keep at least one replica alive, which keeps the node alive, which keeps the NVMe cache warm.

### API Compatibility Strategy

- **OpenAI-compatible endpoints are the primary API surface.** The market converged on OpenAI's API shape — Baseten, vLLM, LiteLLM, Ollama all use it. Don't fight it.
- **Do NOT build Anthropic Messages API or Google Vertex compat.** Those formats are losing the standards war. Clients that need them can use thin adapters.
- **DirectAI-native API for everything else.** Compound pipelines, model deployment/lifecycle, training jobs, and advanced routing have no OpenAI equivalent — this is where DirectAI's differentiation lives.
- **Version the native API from day one** (`/api/v1/`). The OpenAI-compat surface follows OpenAI's versioning.

### Architecture Principles

- **Performance is the product.** Every design decision must justify its latency/throughput impact. "Convenient but slow" is not acceptable.
- **Multi-cloud is not optional.** Cloud-specific code lives behind interfaces. If you can't swap Azure for GCP in a config change, the abstraction is broken.
- **API-first design.** Define OpenAPI specs before writing implementation. The API contract is the product surface.
- **Horizontal scalability.** Stateless request handling. No in-process state that can't be reconstructed or externalized.
- **Fail loud.** No silent swallowing of errors. Structured logging, correlation IDs on every request, circuit breakers on external calls.

### Pricing Architecture

**4 tiers — hybrid billing (base fee + metered per-token usage).** Free (self-hosted OSS / $5 credit) → Pro ($50/mo + metered) → Managed ($3,500/mo + metered) → Enterprise (custom flat fee).

| | Free | Pro ($50/mo + usage) | Managed ($3,500/mo + usage) | Enterprise (Custom) |
|---|---|---|---|---|
| **Base** | $0/mo (self-hosted) or $5 one-time credit (shared API) | $50/mo + per-token usage | $3,500/mo + per-token usage (2× Pro rates) | Custom flat fee (starting $10K/mo) |
| **Compute billing** | Customer pays Azure directly (self-hosted) / included (shared) | Included in per-token rates | Included in per-token rates (DirectAI-owned subscription) | Customer pays Azure directly |
| **Deployment** | Self-service (Helm + Bicep) | Shared DirectAI cluster (`api.agilecloud.ai`) | DirectAI-owned Azure subscription, isolated per customer | Customer's own Azure subscription, DirectAI deploys |
| **Models** | Any OSS model | Curated models (Qwen, Llama, BGE, Whisper) | Any OSS + fine-tuned | + custom model optimization |
| **Rate limits** | 20 RPM / 40K TPM (shared) or N/A (self-hosted) | 300 RPM / 500K TPM | 1,000 RPM / 5M TPM | Custom (default 10K RPM / 100M TPM) |
| **Support** | Community (GitHub Issues) | Email, 48hr SLA | Email, 24hr SLA | Slack + phone, 1hr SLA |
| **SLA** | Best-effort | 99.5% | 99.9% | 99.99% |
| **Compliance** | Customer's responsibility | Standard (data on DirectAI infra) | Shared responsibility (data in DirectAI-owned sub) | HIPAA/SOC 2 documentation provided |
| **Vendor lock-in** | None — Apache 2.0 | None — cancel anytime | None — cancel anytime | None |

**Per-token usage rates (Pro tier):**

| Modality | Metric | Pro | Managed (2×) |
|---|---|---|---|
| Chat — input | per 1M tokens | $1.00 | $2.00 |
| Chat — output | per 1M tokens | $2.00 | $4.00 |
| Embeddings | per 1M tokens | $0.10 | $0.20 |
| Transcription | per minute | $0.10 | $0.20 |

**Key principle:** Pro and Managed are hybrid — base fee covers platform access + support, per-token rates cover compute. Enterprise pays a flat management fee; the customer pays Azure for compute directly. On Free, the $5 credit is consumed at Pro rates until exhausted.

**Target market:** Free/Pro targets developers and startups who want instant API access. Managed targets teams needing isolated infrastructure without managing it themselves. Enterprise targets Azure-first regulated enterprises (healthcare, financial services, government) where data must stay in the customer's own subscription.

**Revenue model:** Base fees (Stripe subscriptions) + per-token metering (Stripe Meters API) for Pro/Managed. Flat contract for Enterprise. Free tier is capped at $5 credit — no ongoing billing.

### Authentication Architecture (Entra External ID)

**Microsoft Entra External ID** is the identity provider for all customer-facing authentication. It runs in a dedicated *external tenant* separate from the DirectAI workforce tenant.

| Component | Detail |
|---|---|
| **Entra External Tenant** | Separate tenant in external configuration. Stores customer user accounts. |
| **Identity Providers** | Microsoft (personal + work/school accounts), Google (native), GitHub (custom OIDC federation), email+password, email+OTP |
| **Login URL** | `https://directai.ciamlogin.com/...` (custom domain target: `auth.agilecloud.ai`) |
| **NextAuth.js v5** | Next.js session management layer. Uses Entra External ID as OIDC provider. |
| **Drizzle Adapter** | `@auth/drizzle-adapter` — stores NextAuth sessions, accounts, users in Postgres. |
| **Pricing** | Free for first 50,000 MAU (monthly active users). |

**Auth flow:**
```
User → agilecloud.ai/login → NextAuth → Entra External ID (OIDC)
  → Microsoft (personal/work) / Google / GitHub / email sign-in
  → Token issued → NextAuth session created (Postgres)
  → Redirect to /dashboard
```

**API key auth (inference):** Separate from dashboard auth. Users generate API keys in the dashboard. Keys are hashed (SHA-256) and stored in Postgres. The API server validates keys against the DB (cached in-memory with TTL).

**Environment variables:**

| Variable | Description |
|---|---|
| `AUTH_SECRET` | NextAuth session encryption secret |
| `AUTH_ENTRA_EXTERNAL_ISSUER` | `https://{subdomain}.ciamlogin.com/{tenant-id}/v2.0` |
| `AUTH_ENTRA_EXTERNAL_CLIENT_ID` | App registration client ID in external tenant |
| `AUTH_ENTRA_EXTERNAL_CLIENT_SECRET` | App registration client secret |

**Setup steps (manual, one-time):**
1. Create Entra External ID tenant in Azure Portal (Microsoft Entra admin center → External Identities → External tenants).
2. Register app (`directai-web`) in the external tenant — supported account types: **Accounts in any organizational directory and personal Microsoft accounts**. Redirect URI: `https://agilecloud.ai/api/auth/callback/entra-external`.
3. Configure user flow: sign-up + sign-in, enable Microsoft (personal + work/school), Google, and email+OTP.
4. Add GitHub as custom OIDC identity provider (GitHub OAuth app → OIDC well-known endpoint via GitHub's OIDC support).
5. Store client ID and secret in Platform Key Vault. Reference via workload identity in AKS pods.

### Billing Architecture (Stripe)

**Stripe Meters API** for usage-based billing. Stripe handles invoicing, payment processing, and subscription lifecycle.

| Component | Where | Purpose |
|---|---|---|
| **Stripe Customer sync** | Web app (server action) | Create Stripe customer on first sign-in via NextAuth callback |
| **Subscription management** | Web app (Stripe Checkout / Customer Portal) | Tier selection, upgrade/downgrade, payment method |
| **API key management** | Web app + API server | Generate, list, revoke keys. Keys stored SHA-256 hashed in Postgres. |
| **Usage metering** | API server middleware | Count tokens per request, emit structured usage events |
| **Usage reporter** | Background worker (cron or sidecar) | Batch-report usage events to Stripe Meters API every 60s |
| **Dashboard** | Web app (`/dashboard`) | Current usage, spend, invoices, API keys |

**Billing flow:**
```
User signup (Entra + NextAuth)
  → Stripe Customer created (linked to user.id)
  → User picks tier → Stripe Checkout Session → Subscription created
  → User generates API key → key_hash stored in Postgres
  → API requests hit api-server → middleware counts tokens
  → Usage events written to Postgres usage_records table
  → Background worker batches usage → Stripe Meters API
  → Stripe calculates bill → charges card monthly
```

**Environment variables:**

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe API secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (client-side) |
| `STRIPE_WEBHOOK_SECRET` | Webhook endpoint signing secret |
| `DIRECTAI_STRIPE_METER_CHAT_INPUT` | Stripe Meter event name for chat input tokens (default: `chat_input_tokens`) |
| `DIRECTAI_STRIPE_METER_CHAT_OUTPUT` | Stripe Meter event name for chat output tokens (default: `chat_output_tokens`) |
| `DIRECTAI_STRIPE_METER_EMBEDDING` | Stripe Meter event name for embedding tokens (default: `embedding_tokens`) |
| `DIRECTAI_STRIPE_METER_TRANSCRIPTION` | Stripe Meter event name for transcription (default: `transcription_seconds`) |

### Database (PostgreSQL + Drizzle ORM)

**Azure Database for PostgreSQL Flexible Server** in the Platform resource group. Accessed by the web app via connection string (workload identity or password auth).

| Config | Dev | Prod |
|---|---|---|
| **SKU** | Burstable B1ms (1 vCore, 2 GB) | GeneralPurpose D2s_v3 (2 vCore, 8 GB) |
| **Storage** | 32 GB | 256 GB |
| **HA** | Disabled | Zone-redundant |
| **Backup** | 7 days, no geo | 35 days, geo-redundant |
| **Access** | Public + Azure firewall | Private endpoint (AKS VNet) |
| **Auth** | Password + Entra admin | Entra-only (workload identity) |
| **Version** | PostgreSQL 17 | PostgreSQL 17 |

**ORM:** Drizzle ORM (TypeScript-native, lightweight, SQL-first). Migrations via `drizzle-kit`.

**Schema (6 tables):**

| Table | Purpose |
|---|---|
| `users` | NextAuth-managed. id, name, email, emailVerified, image. |
| `accounts` | NextAuth-managed. OAuth provider accounts linked to users. |
| `sessions` | NextAuth-managed. Active user sessions. |
| `verification_tokens` | NextAuth-managed. Email verification / magic links. |
| `api_keys` | DirectAI. id, userId, keyHash, keyPrefix, name, createdAt, lastUsedAt, revokedAt. |
| `usage_records` | DirectAI. id, userId, apiKeyId, model, modality, inputTokens, outputTokens, requestId, createdAt. |

**Connection string env var:** `DATABASE_URL=postgresql://directaiadmin:{password}@{server}.postgres.database.azure.com:5432/directai?sslmode=require`

**Bicep:** Deployed via `infra/platform/main.bicep` using AVM module `br/public:avm/res/db-for-postgre-sql/flexible-server`. Conditional on `enablePlatformDb = true`.

## Development Guidelines

### Repository Structure

```
DirectAI/
├── .github/
│   ├── copilot-instructions.md       # This file
│   └── workflows/
│       ├── onboard-customer.yml      # Automated customer onboarding pipeline
│       ├── deploy-platform.yml       # Shared platform infra (ACR, engine cache, monitoring, Platform AKS)
│       ├── deploy-stamp.yml          # Regional stamp deployment pipeline
│       ├── build-api-server.yml      # CI: lint, test, build API server image
│       ├── build-web.yml             # CI: lint, build web image, optional Helm deploy
│       ├── build-engines.yml         # CI: build embeddings + TRT-LLM engine images
│       ├── compile-engine.yml        # Compile TRT-LLM engine for model × GPU SKU
│       ├── deploy-model.yml          # Deploy model to customer AKS cluster
│       └── populate-cache.yml        # Pre-compile engines for popular architectures
├── infra/                            # All Bicep IaC lives here
│   ├── main.bicep                    # Stamp orchestrator — single entry point
│   ├── modules/
│   │   ├── acr-role-assignment.bicep # Reusable AcrPull role assignment
│   │   ├── dns-record.bicep         # DNS A record helper
│   │   └── workbook.bicep           # Azure Workbook module
│   ├── platform/                     # Shared platform infra (operations subscription)
│   │   ├── main.bicep                # ACR, engine cache, monitoring, DNS, Platform AKS, PostgreSQL
│   │   └── environments/
│   │       ├── platform.dev.eus2.bicepparam
│   │       └── platform.prod.eus2.bicepparam
│   ├── customers/                    # Customer manifests (one JSON per customer)
│   │   └── _example.commercial.json
│   └── environments/                 # Per-environment, per-region parameter files
│       ├── internal.dev.scus.bicepparam  # Dev stamp — South Central US, T4 GPU
│       ├── internal.dev.eus2.bicepparam
│       ├── internal.prod.eus2.bicepparam
│       └── {customerId}.{env}.{region}.bicepparam
├── src/
│   ├── api-server/                   # OpenAI-compatible API gateway (routing proxy)
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI app, lifespan, health probes
│   │   │   ├── config.py             # pydantic-settings, DIRECTAI_ env prefix
│   │   │   ├── telemetry.py          # OpenTelemetry setup (Azure Monitor + OTLP exporters)
│   │   │   ├── metrics.py            # Prometheus metrics (inflight, latency, request counts)
│   │   │   ├── auth/
│   │   │   │   └── api_key.py        # Bearer token auth — DB-backed with in-memory TTL cache
│   │   │   ├── billing/
│   │   │   │   └── __init__.py       # Stripe usage reporter background worker
│   │   │   ├── middleware/
│   │   │   │   ├── correlation_id.py # X-Request-ID propagation
│   │   │   │   ├── request_logging.py# Structured JSON request logging
│   │   │   │   └── rate_limit.py     # Token-bucket rate limiter per API key/IP
│   │   │   ├── models/               # Model lifecycle (SQLite-backed)
│   │   │   │   ├── domain.py         # Domain models (ModelVersion, Deployment, EngineCache)
│   │   │   │   └── repository.py     # SQLite repository for model/deployment/engine CRUD
│   │   │   ├── routes/
│   │   │   │   ├── chat_completions.py   # POST /v1/chat/completions (model name rewriting)
│   │   │   │   ├── embeddings.py         # POST /v1/embeddings (model name rewriting)
│   │   │   │   ├── audio_transcriptions.py # POST /v1/audio/transcriptions
│   │   │   │   ├── models.py            # GET /v1/models
│   │   │   │   ├── native_models.py     # /api/v1/models — model lifecycle CRUD
│   │   │   │   ├── native_deployments.py # /api/v1/deployments — deployment CRUD
│   │   │   │   ├── native_engine_cache.py # /api/v1/engine-cache — compiled engine registry
│   │   │   │   └── native_system.py     # /api/v1/system — health, capacity, metrics
│   │   │   ├── routing/
│   │   │   │   ├── model_registry.py # YAML → ModelSpec, alias resolution
│   │   │   │   └── backend_client.py # httpx async HTTP/2 proxy client
│   │   │   └── schemas/
│   │   │       ├── chat.py           # ChatCompletion request/response/chunk
│   │   │       ├── embeddings.py     # Embedding request/response
│   │   │       ├── audio.py          # Transcription request/response
│   │   │       └── models.py         # Model list response
│   │   ├── tests/
│   │   │   ├── conftest.py           # Fixtures: test model YAMLs, TestClient
│   │   │   ├── test_chat.py
│   │   │   ├── test_embeddings.py
│   │   │   ├── test_health.py
│   │   │   ├── test_models.py
│   │   │   ├── test_audio.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_correlation_id.py
│   │   │   ├── test_engine_cache.py
│   │   │   ├── test_integration_proxy.py
│   │   │   ├── test_metrics.py
│   │   │   ├── test_native_deployments.py
│   │   │   ├── test_native_models.py
│   │   │   ├── test_native_system.py
│   │   │   ├── test_rate_limit.py
│   │   │   ├── test_sensitive_data.py
│   │   │   └── test_tracing.py
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── embeddings-engine/            # ONNX Runtime GPU embedding inference server
│   │   ├── engine/
│   │   │   ├── config.py             # EMBED_ env prefix, model/batch config
│   │   │   ├── model.py             # ONNX session, tokenize, mean pool, L2 norm
│   │   │   ├── batcher.py           # Async dynamic batcher (queue → GPU batch)
│   │   │   ├── metrics.py           # Prometheus: inflight, latency, batch size
│   │   │   ├── main.py              # FastAPI: /v1/embeddings, health, metrics
│   │   │   └── export.py            # HuggingFace → ONNX export utility
│   │   ├── Dockerfile               # Multi-stage: optional model bake + runtime
│   │   └── pyproject.toml
│   ├── trtllm-engine/                # TensorRT-LLM chat/completion inference server
│   │   ├── engine/
│   │   │   ├── config.py             # TRTLLM_ env prefix, TP/PP, KV cache config
│   │   │   ├── runner.py             # TRT-LLM HLAPI wrapper, stub mode for dev
│   │   │   ├── chat_format.py        # Chat template + OpenAI response formatting
│   │   │   ├── metrics.py            # Prometheus: TTFT, latency, token counts
│   │   │   └── main.py              # FastAPI: /v1/chat/completions (SSE + sync)
│   │   ├── Dockerfile               # NVIDIA TRT-LLM base + MPI entrypoint
│   │   └── pyproject.toml
│   └── web/                          # Next.js marketing + dashboard site (agilecloud.ai)
│       ├── src/
│       │   ├── middleware.ts         # NextAuth middleware — protects /dashboard/*
│       │   ├── app/
│       │   │   ├── page.tsx          # Landing page — hero, features, code sample
│       │   │   ├── layout.tsx        # Root layout — dark theme, Inter/Geist fonts, LinkedIn Insight Tag
│       │   │   ├── globals.css       # Tailwind v4 imports
│       │   │   ├── pricing/page.tsx  # Pricing tiers
│       │   │   ├── waitlist/page.tsx # Waitlist signup (server action)
│       │   │   ├── login/            # NextAuth sign-in page
│       │   │   ├── dashboard/        # Authenticated dashboard
│       │   │   │   ├── page.tsx      # Dashboard overview
│       │   │   │   ├── layout.tsx    # Dashboard layout with sidebar
│       │   │   │   ├── api-keys/     # API key management (create/revoke)
│       │   │   │   ├── billing/      # Stripe billing portal
│       │   │   │   └── usage/        # Usage statistics
│       │   │   ├── privacy/page.tsx  # Privacy policy
│       │   │   ├── terms/page.tsx    # Terms of service
│       │   │   └── api/auth/         # NextAuth API routes
│       │   ├── components/
│       │   │   ├── navbar.tsx        # Auth-aware navbar (useSession, signOut)
│       │   │   ├── footer.tsx        # Site footer
│       │   │   ├── conditional-footer.tsx # Footer that hides on dashboard
│       │   │   ├── dashboard-sidebar.tsx  # Dashboard navigation sidebar
│       │   │   └── session-provider.tsx   # NextAuth SessionProvider wrapper
│       │   └── lib/
│       │       ├── auth.ts           # NextAuth v5 config — Entra External ID OIDC
│       │       ├── db/
│       │       │   ├── index.ts      # Drizzle ORM client
│       │       │   └── schema.ts     # Drizzle schema (users, accounts, sessions, api_keys, etc.)
│       │       ├── stripe/
│       │       │   ├── client.ts     # Stripe SDK client
│       │       │   ├── customers.ts  # Stripe customer sync logic
│       │       │   └── index.ts      # Stripe exports
│       │       ├── utils.ts          # Shared utilities
│       │       └── waitlist-store.ts # Waitlist email persistence
│       ├── Dockerfile                # Multi-stage: deps → build → node:22-alpine runner
│       ├── package.json              # Next.js 16.1, React 19, Tailwind v4, NextAuth v5
│       └── next.config.ts            # output: 'standalone'
├── deploy/
│   ├── cluster-issuers.yaml          # cert-manager ClusterIssuers (staging + prod)
│   ├── models/                       # ModelDeployment YAML configs (one per model)
│   │   ├── qwen2.5-3b-instruct.yaml # vLLM — active on dev T4 GPU
│   │   ├── bge-large-en-v1.5.yaml   # ONNX Runtime — active on dev T4 GPU
│   │   ├── llama-3.1-70b-instruct.yaml  # TRT-LLM — A100/H100 target
│   │   ├── whisper-large-v3.yaml     # TRT-LLM — STT target
│   │   ├── local/                    # Ollama-based local dev model configs
│   │   │   ├── llama3.2-3b.yaml
│   │   │   ├── nomic-embed-text.yaml
│   │   │   └── README.md
│   │   └── README.md
│   └── helm/                         # Helm chart for K8s deployment
│       └── directai/
│           ├── Chart.yaml
│           ├── values.yaml           # Base defaults
│           ├── values-dev.yaml       # Dev stamp overrides (T4 GPU, vLLM)
│           ├── values-platform.yaml  # Platform AKS — web only, inference off
│           └── templates/            # 24 templates inc. web-*, backend-*, api-server-*
├── docker-compose.yml                # Local multi-service development
├── scripts/
│   ├── bootstrap-oidc.ps1           # One-time OIDC identity bootstrap
│   └── export-openapi.py           # Export OpenAPI spec from API server
```

### Application Layer — API Server

The API server is a **stateless routing proxy** that sits between clients and inference backend pods. It does NOT run inference — it resolves model names, validates requests, and proxies traffic to the correct backend service.

**Stack:** Python 3.11, FastAPI, httpx (HTTP/2), Pydantic v2, pydantic-settings, PyYAML, uvicorn.

#### OpenAI-Compatible Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Chat completions — streaming (SSE) + non-streaming. Proxied to vLLM (dev/staging) or TRT-LLM (prod) backend. Model name rewritten to backend's expected name. |
| `POST` | `/v1/embeddings` | Text embeddings. Proxied to ONNX Runtime backend. Model name rewritten. |
| `POST` | `/v1/audio/transcriptions` | Audio transcription (multipart). Proxied to TRT-LLM Whisper backend. |
| `GET`  | `/v1/models` | Lists all registered models (every alias is a separate entry). |
| `GET`  | `/healthz` | Liveness probe — always 200. |
| `GET`  | `/readyz` | Readiness probe — 200 if models loaded, 503 otherwise. |

#### Request Flow

```
Client → API Server (auth → rate limit → correlation ID → logging → route handler)
  → ModelRegistry.resolve(model_name)     # alias lookup → ModelSpec
  → payload["model"] = model_spec.name    # rewrite to backend's expected model name
  → BackendClient.post_json/post_stream   # proxy to http://{svc}.directai.svc.cluster.local:8001
  → Inference backend (vLLM / ONNX Runtime / TRT-LLM)
  → Response streamed back to client
```

#### DirectAI Native API Endpoints

Purpose-built endpoints for model lifecycle, deployment management, engine cache, and system health. These have no OpenAI equivalent.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/models` | Register a new model version |
| `GET` | `/api/v1/models` | List models (filterable by modality, owner) |
| `GET/PATCH/DELETE` | `/api/v1/models/{id}` | Model lifecycle CRUD |
| `POST` | `/api/v1/deployments` | Create a deployment for a model version |
| `GET` | `/api/v1/deployments` | List deployments (filterable) |
| `GET/PATCH/DELETE` | `/api/v1/deployments/{id}` | Deployment lifecycle CRUD |
| `POST` | `/api/v1/engine-cache` | Register a compiled engine artifact |
| `GET` | `/api/v1/engine-cache` | List cached engines |
| `GET` | `/api/v1/engine-cache/lookup` | Lookup engine by architecture + GPU SKU + quantization |
| `GET` | `/api/v1/system/health` | Service health snapshot (model registry + backend liveness) |
| `GET` | `/api/v1/system/capacity` | GPU pool capacity and utilization |
| `GET` | `/api/v1/system/metrics` | Prometheus-format metrics |

#### Model Registry

The `ModelRegistry` loads `ModelDeployment` YAML files from a directory at startup and builds an in-memory alias index.

- Each YAML defines: metadata name, display name, owned_by, modality (`chat`/`embedding`/`transcription`), engine config, hardware requirements, scaling policy, and API aliases.
- `resolve(model_name)` does **case-insensitive** alias lookup → returns `ModelSpec` or `None`.
- Backend URL pattern: `http://{service-name}.{namespace}.svc.cluster.local:{port}` (defaults: namespace=`directai`, port=`8001`).
- Config directory is set via `DIRECTAI_MODEL_CONFIG_DIR` env var (default: `/app/models`).

#### Configuration (Environment Variables)

All settings use the `DIRECTAI_` prefix.

| Variable | Default | Description |
|---|---|---|
| `DIRECTAI_HOST` | `0.0.0.0` | Bind address |
| `DIRECTAI_PORT` | `8000` | Bind port |
| `DIRECTAI_LOG_LEVEL` | `info` | Log level (debug/info/warning/error) |
| `DIRECTAI_MODEL_CONFIG_DIR` | `/app/models` | Path to ModelDeployment YAML directory |
| `DIRECTAI_API_KEYS` | *(empty)* | Comma-separated API keys. Empty = auth disabled (dev only) |
| `DIRECTAI_BACKEND_TIMEOUT` | `300` | Backend request timeout (seconds) |
| `DIRECTAI_BACKEND_CONNECT_TIMEOUT` | `5` | Backend connect-phase timeout (seconds) |
| `DIRECTAI_DATABASE_URL` | *(empty)* | PostgreSQL connection for key validation + usage metering |
| `DIRECTAI_KEY_CACHE_TTL` | `60` | API key in-memory cache TTL (seconds) |
| `DIRECTAI_STRIPE_SECRET_KEY` | *(empty)* | Stripe API secret key. Empty = dry-run mode (events logged, not sent) |
| `DIRECTAI_USAGE_REPORT_INTERVAL` | `60` | Seconds between Stripe Meter flush cycles |
| `DIRECTAI_STRIPE_METER_CHAT_INPUT` | `chat_input_tokens` | Stripe Meter event name for chat input tokens |
| `DIRECTAI_STRIPE_METER_CHAT_OUTPUT` | `chat_output_tokens` | Stripe Meter event name for chat output tokens |
| `DIRECTAI_STRIPE_METER_EMBEDDING` | `embedding_tokens` | Stripe Meter event name for embedding tokens |
| `DIRECTAI_STRIPE_METER_TRANSCRIPTION` | `transcription_seconds` | Stripe Meter event name for transcription (centiseconds) |
| `DIRECTAI_OTEL_ENABLED` | `true` | Enable OpenTelemetry tracing |
| `DIRECTAI_APPINSIGHTS_CONNECTION_STRING` | *(empty)* | Azure Application Insights connection string |
| `DIRECTAI_OTLP_ENDPOINT` | *(empty)* | OTLP gRPC endpoint for trace export |
| `DIRECTAI_OTEL_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0–1.0) |
| `DIRECTAI_RATE_LIMIT_RPS` | `60` | Per-key rate limit (requests/second) |
| `DIRECTAI_RATE_LIMIT_BURST` | `120` | Token-bucket burst capacity |
| `DIRECTAI_DATABASE_PATH` | *(empty)* | SQLite path for model lifecycle state |

#### Auth

- Bearer token via `Authorization: Bearer <key>` header.
- **Auth is disabled when `DIRECTAI_API_KEYS` is empty** — dev mode only, never in production.
- Returns 401 with `WWW-Authenticate: Bearer` on failure.

#### Observability

- **Correlation IDs:** Every request gets an `X-Request-ID` (from client header or auto-generated UUID). Propagated through logs and response headers.
- **Structured logging:** JSON format — `ts`, `level`, `logger`, `msg`, `method`, `path`, `status_code`, `duration_ms`, `request_id`.
- **Error responses:** OpenAI-compatible error JSON with `X-Request-ID` header.

#### Running Locally

```bash
cd src/api-server
pip install -e ".[dev]"
DIRECTAI_MODEL_CONFIG_DIR=../../deploy/models python -m uvicorn app.main:app --reload
```

#### Running Tests

```bash
cd src/api-server
python -m pytest tests/ -v
```

### Known Issues & Operational Notes

#### vLLM CUDA Compatibility on AKS T4 Nodes (CRITICAL)

vLLM `cu130` containers ship a bundled CUDA compat library at `/usr/local/cuda-13.0/compat/libcuda.so.1` (version `580.82.07`). AKS T4 nodes mount the host NVIDIA driver at `/lib/x86_64-linux-gnu/libcuda.so.1` (version `580.95.05`). When `LD_LIBRARY_PATH` is empty, the container's compat lib resolves first. The minor version mismatch (`580.82.07` userspace vs `580.95.05` kernel) produces **CUDA Error 803: system has unsupported display driver / cuda driver combination**.

**Fix:** Set `LD_LIBRARY_PATH=/lib/x86_64-linux-gnu` in the vLLM container environment. This forces the host-mounted driver to be found first, matching the kernel driver version.

This is configured in `values-dev.yaml` under the vLLM backend's `env` block. **Do not remove this env var** — it is required for any vLLM `cu*` image on AKS nodes.

**Note:** `VLLM_ENABLE_CUDA_COMPATIBILITY=1` does NOT fix this issue. The compat flag bridges CUDA toolkit versions, not minor driver version mismatches.

### Inference Engines

The API server is a routing proxy — it does NOT run inference. Actual inference runs in dedicated engine containers on GPU pods.

#### Embeddings Engine (`src/embeddings-engine/`)

ONNX Runtime GPU server for embedding/reranking models. Optimized for high-throughput batch parallelism.

**Stack:** Python 3.11, FastAPI, ONNX Runtime GPU, HuggingFace tokenizers (Rust), prometheus-client.

| Component | Purpose |
|---|---|
| `engine/model.py` | ONNX session, tokenization, mean pooling, L2 normalization |
| `engine/batcher.py` | Async dynamic batcher — collects requests into GPU-efficient batches |
| `engine/export.py` | HuggingFace → ONNX export with optional FP16 conversion |
| `engine/main.py` | FastAPI: `POST /v1/embeddings`, health probes, metrics |

**Key design:** Dynamic batching via asyncio queue. Requests accumulate up to `max_batch_size` (256) or `batch_timeout_ms` (5ms), then fire as a single GPU batch. Individual futures scatter results back.

**Config prefix:** `EMBED_` — model_path, tokenizer_path, max_seq_length (512), max_batch_size (256), execution_provider (CUDAExecutionProvider).

#### TRT-LLM Engine (`src/trtllm-engine/`)

TensorRT-LLM inference server for LLMs and STT. Wraps TRT-LLM's High-Level API behind an OpenAI-compatible HTTP interface.

**Stack:** Python 3.11, FastAPI, TensorRT-LLM (HLAPI), HuggingFace transformers (tokenizer), prometheus-client.

| Component | Purpose |
|---|---|
| `engine/runner.py` | TRT-LLM HLAPI wrapper — deferred import, stub mode when not installed |
| `engine/chat_format.py` | Chat template application + OpenAI ChatCompletion format conversion |
| `engine/main.py` | FastAPI: `POST /v1/chat/completions` (SSE + non-streaming), health, metrics |
| `engine/metrics.py` | Prometheus: TTFT, latency, inflight, prompt/completion token counts |

**Key design:** TRT-LLM import is deferred — the engine runs in stub mode when `tensorrt_llm` isn't installed, so the codebase can be developed and tested without GPU hardware. Production runs inside NVIDIA TRT-LLM containers with pre-compiled engines mounted at `/models`.

**Config prefix:** `TRTLLM_` — engine_dir, tokenizer_dir, tp_size, pp_size, kv_cache_free_gpu_mem_fraction (0.85), max_batch_size (64).

**Metrics:** `directai_llm_time_to_first_token_seconds`, `directai_llm_request_duration_seconds`, `directai_llm_tokens_generated_total`, `directai_llm_prompt_tokens_total`, `directai_llm_inflight_requests`.

### Web Frontend (`src/web/`)

Next.js marketing and dashboard site served at `https://agilecloud.ai`.

**Stack:** Next.js 16.1, React 19, Tailwind CSS v4, TypeScript, NextAuth v5, Drizzle ORM, standalone output mode.

**Pages:**

| Route | Description |
|---|---|
| `/` | Landing page — hero section, features grid, live code sample, CTA |
| `/pricing` | Pricing tiers (Starter / Pro / Enterprise) |
| `/waitlist` | Email signup form with server action |
| `/login` | NextAuth sign-in page (redirects to Entra External ID) |
| `/dashboard` | Authenticated dashboard — overview, plan info |
| `/dashboard/api-keys` | API key management (create / revoke) |
| `/dashboard/billing` | Stripe billing portal integration |
| `/dashboard/usage` | Usage statistics and token consumption |
| `/privacy` | Privacy policy |
| `/terms` | Terms of service |
| `/api/auth/[...nextauth]` | NextAuth API routes (callbacks, session, CSRF) |

**Authentication:** NextAuth v5 with Entra External ID OIDC provider. JWT session strategy. `middleware.ts` protects `/dashboard/*` routes. `SessionProvider` wrapper for client-side session access.

**Components:** Auth-aware `navbar.tsx` (useSession, signOut), `dashboard-sidebar.tsx`, `conditional-footer.tsx` (hides on dashboard routes), `session-provider.tsx`.

**Analytics:** LinkedIn Insight Tag (partner ID `8912820`) embedded in root layout.

**Dockerfile:** Multi-stage build — `deps` (install node_modules) → `builder` (next build) → `runner` (node:22-alpine, standalone output, port 3000).

**Deployment:** Runs on Platform AKS via Helm (`values-platform.yaml`). 2 replicas behind NGINX Ingress with Let's Encrypt TLS. Image: `acrplatformdaiv7fgid.azurecr.io/web:latest`.

**CI:** `build-web.yml` — triggers on `src/web/**` changes, builds Docker image via `az acr build`, pushes to platform ACR, optional Helm deploy to Platform AKS.

### Helm Chart (`deploy/helm/directai/`)

Single Helm chart for all DirectAI Kubernetes deployments. 24 templates covering:

| Template Group | Templates | Purpose |
|---|---|---|
| **web-*** | `web-deployment.yaml`, `web-service.yaml`, `web-ingress.yaml`, `_web-helpers.tpl` | Next.js web app with TLS ingress |
| **api-server-*** | `api-server-deployment.yaml`, `api-server-service.yaml`, `api-server-ingress.yaml`, `_api-server-helpers.tpl` | API gateway proxy |
| **backend-*** | `backend-deployment.yaml`, `backend-service.yaml`, `backend-hpa.yaml`, `_backend-helpers.tpl` | Inference engine pods (per model) |
| **common** | `namespace.yaml`, `configmap.yaml`, `secrets.yaml`, `serviceaccount.yaml`, `networkpolicy.yaml`, etc. | Shared K8s resources |

**Values files:**

| File | Purpose |
|---|---|
| `values.yaml` | Base defaults |
| `values-dev.yaml` | Dev stamp overrides (T4 GPU, scale-to-zero) |
| `values-platform.yaml` | Platform AKS — web enabled (2 replicas), apiServer replicas 0, inference disabled, host `agilecloud.ai`, cert-manager issuer `letsencrypt-prod` |

### Model Deployment Config Schema

Models are declared as YAML files using the `directai/v1 ModelDeployment` kind. See `deploy/models/README.md` for the full field reference.

```yaml
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: <k8s-service-name>     # Becomes the K8s Service name
spec:
  displayName: "<human-readable>"
  ownedBy: <org>
  modality: chat | embedding | transcription
  engine:
    type: tensorrt-llm | onnxruntime | vllm | ollama
    image: "<registry>/<image>:<tag>"
    backendUrl: "<optional URL override — local dev / Ollama only>"
    weightsUri: "az://<container>/<path>"
    maxBatchSize: <int>         # Embeddings only
  hardware:
    gpuSku: <azure-vm-sku>
    gpuCount: <int>
    nvmeCacheEnabled: true|false
  scaling:
    tier: always-warm | scale-to-zero
    minReplicas: <int>
    maxReplicas: <int>
    targetConcurrency: <int>
  api:
    aliases:                    # All names this model responds to
      - <alias-1>
      - <org>/<alias-2>
```

### Multi-Subscription Customer Isolation

Each customer gets their own Azure subscription. This is the isolation boundary — billing, networking, identity, and blast radius are all per-subscription.

**Operations subscription: `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9`** — this is the centralized subscription for all shared DirectAI platform services.

| Subscription | Owner | Subscription ID | Contains |
|---|---|---|---|
| **Operations (Platform)** | DirectAI | `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9` | Shared ACR (inference images), engine cache Storage Account, centralized Log Analytics + Application Insights, CI/CD identity, monitoring dashboards |
| **Internal Dev** | DirectAI | `0ae2be9a-f470-4dfe-b2e0-b7e9726acdfb` | Dev stamp (South Central US): AKS with T4 GPU pool (`gpuPoolTier: 'dev'`), Storage, Key Vault, VNet, Log Analytics |
| **Customer N** | DirectAI (on behalf of customer) | Per-customer GUID | Regional stamp(s): AKS, Storage (model weights), Key Vault, VNet, per-stamp Log Analytics, customer-specific managed identities |

#### Platform Infrastructure (`infra/platform/main.bicep`)

Shared resources deployed to the operations subscription. Deployed via the **Deploy Platform** workflow (`deploy-platform.yml`).

| Resource | Purpose | Cross-Sub Access |
|---|---|---|
| **ACR** (Premium) `acrplatformdaiv7fgid` | All inference + web images — api-server, embeddings-engine, trtllm-engine, web | Customer kubelet identities get `AcrPull` |
| **Storage Account** `stplatformdaiv7fgid` | Pre-compiled TRT-LLM engine cache (`engine-cache` container), model registry, build artifacts | Customer stamps read via SAS or Blob Reader |
| **Log Analytics** | Centralized monitoring sink — aggregates across all stamps | Customer stamps can forward diagnostics here |
| **Application Insights** | Distributed tracing + live metrics for the platform as a whole | API server pods emit traces via connection string |
| **DNS Zone** `agilecloud.ai` | Public DNS zone — A records for web + API subdomains. Records managed in Bicep: `@` + `www` → Platform AKS IP, `api` → Dev AKS IP | All clusters reference this zone |
| **Platform AKS** `aks-dai-platform-dev-eus2` | CPU-only cluster for web app, metering, webhooks. K8s 1.33. | N/A — platform-only |
| **Platform Key Vault** | Stripe keys, NextAuth secret, DB connection strings | Platform AKS workload identity |
| **Platform PostgreSQL** | NextAuth sessions, user accounts, API keys, usage records. Conditional on `enablePlatformDb = true`. | Platform AKS via connection string |
| **Platform VNet** (`10.200.0.0/16`) | Networking for Platform AKS — system subnet + CPU node pool subnet | N/A |
| **Platform Managed Identities** | Control plane + kubelet identities for Platform AKS (same split as stamps) | Kubelet gets AcrPull, Storage Blob Data Contributor, Key Vault Secrets User |

**Platform AKS** is conditional on `enablePlatformAks = true` in the parameter file. It is a CPU-only cluster (no GPU pools) running:
- NGINX Ingress Controller (external IP: `4.153.165.222`)
- cert-manager v1.19 with Let's Encrypt prod ClusterIssuer
- DirectAI web app (Next.js) — `directai-platform` Helm release in `directai` namespace

The `platform` GitHub environment holds OIDC credentials for this subscription:
- `PLATFORM_AZURE_CLIENT_ID` — used by build + deploy-platform workflows
- `PLATFORM_AZURE_TENANT_ID`
- `PLATFORM_AZURE_SUBSCRIPTION_ID` = `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9`
- `vars.ACR_NAME` — set after first deploy-platform run
- `vars.ACR_LOGIN_SERVER` — set after first deploy-platform run

- **Customer manifest files** (`infra/customers/{customerId}.json`) map customer → subscription ID, `operationsSubscriptionId`, allowed regions, GPU tier, platform ACR reference, contacts.
- **Platform ACR** holds all inference images (DirectAI IP). Commercial customers' kubelet identities get cross-subscription `AcrPull`. Customers that need isolation (air-gap, sovereignty) deploy their own ACR by omitting `platformAcrLoginServer`.
- **GPU quotas** are per-subscription. Each new customer subscription requires quota requests for their GPU tier before `enableGpuPools = true`.
- **Cost isolation** is free — Azure billing is per-subscription. Tag everything with `customer-id` for drill-down.

### Identity Architecture

Two user-assigned managed identities per stamp, split for least privilege:

| Identity | Name Pattern | AKS Role | RBAC |
|---|---|---|---|
| **Control Plane** | `id-cp-dai-{customer}-{env}-{region}` | `managedIdentities` | Managed Identity Operator on kubelet identity |
| **Kubelet** | `id-kubelet-dai-{customer}-{env}-{region}` | `identityProfile.kubeletidentity` | AcrPull (ACR), Storage Blob Data Contributor (Storage), Key Vault Secrets User (Key Vault) |

Kubelet identity gets **read-only** Key Vault access (Secrets User, not Secrets Officer). If a node is compromised, the attacker can read secrets but can't write or delete them.

### Infrastructure as Code (Bicep)

- **Azure Verified Modules (AVM)** from the Bicep public registry are the building blocks. Never write raw resource definitions when an AVM module exists.
- **Two Bicep entry points:**
  - `infra/platform/main.bicep` — shared platform resources (ACR, engine cache, centralized monitoring) deployed to the operations subscription `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9`.
  - `infra/main.bicep` — customer stamp (AKS, Storage, Key Vault, VNet, per-stamp monitoring, identities) deployed to the customer's subscription.
- **One stamp = one `infra/main.bicep`** deployment. A stamp is the complete set of Azure resources for one customer region: VNet, AKS, Storage, (optional) ACR, Key Vault, Log Analytics, 2 Managed Identities.
- **Naming convention:** `dai-{customerId}-{env}-{regionShort}` for stamps, `dai-platform-{env}-{regionShort}` for platform resources. Length-constrained names (Key Vault, Storage, ACR) use a deterministic 8-char hash via `uniqueString()`.
- **Parameter files:** `.bicepparam` format (not JSON). One file per environment × region: `{env}.{regionShort}.bicepparam`. Platform params live in `infra/platform/environments/`.
- **GPU pools are conditional:** `enableGpuPools = false` for dev (avoids GPU quota issues), `true` for prod.
- **ACR is conditional:** `platformAcrLoginServer` parameter controls whether the stamp deploys its own ACR or uses the shared platform ACR.
- **Resource group per stamp:** `rg-dai-{customer}-{env}-{regionShort}`. Platform: `rg-dai-platform-{env}-{regionShort}`.

### Security Baseline (All Customers)

- **TLS 1.2 minimum** on all PaaS endpoints (Storage, Key Vault).
- **No public blob access.** Shared key access disabled on storage accounts.
- **RBAC authorization** on Key Vault (no access policies).
- **Soft delete + purge protection** on Key Vault (90-day retention).
- **Entra ID authentication only** on AKS — local accounts disabled, Azure RBAC for K8s authz.
- **Network policy enforced** — Azure CNI with Azure network policy.
- **Auto-upgrade enabled** — stable channel for AKS, SecurityPatch for node OS.
- **Maintenance windows** — Sunday 04:00 UTC, 4-hour window.
- **Diagnostic logging** — API server, controller manager, scheduler, cluster autoscaler all sent to Log Analytics.

### Adding a New Customer

Customer onboarding is **fully automated** via the `Onboard Customer` workflow (`onboard-customer.yml`). Run it from GitHub Actions → workflow_dispatch with these inputs:

| Input | Description |
|---|---|
| `display_name` | Human-readable company name |
| `billing_scope` | EA enrollment account resource ID (for subscription creation) |
| `regions` | Comma-separated Azure regions (e.g., `eastus2,westus3`) |
| `gpu_tier` | `starter`, `enterprise`, or `dedicated` |
| `use_platform_acr` | `true` for shared ACR, `false` for air-gapped/sovereign |
| `contact_technical` | Technical contact email |
| `contact_billing` | Billing contact email |
| `existing_subscription_id` | Optional — skip subscription creation if already provisioned |

**What the workflow does (zero manual steps):**

1. **Generates customer ID** — new GUID.
2. **Validates** — region names.
3. **Creates Azure Subscription** — under the billing enrollment account (or uses existing).
4. **Creates App Registration** — `sp-dai-{customerId}` with Service Principal in Entra ID.
5. **Creates OIDC Federated Credentials** — one per GitHub environment (`{customerId}-dev`, `{customerId}-prod`).
6. **Assigns RBAC** — `Contributor` + `User Access Administrator` on the new subscription.
7. **Creates GitHub Environments** — with `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` secrets.
8. **Commits files** — customer manifest (`infra/customers/{customerId}.json`) and Bicep parameter files (`infra/environments/{customerId}.{env}.{region}.bicepparam`).

**After the workflow completes:**

1. Configure **required reviewers** on `{customerId}-prod` in GitHub repo → Settings → Environments.
2. Run the **Deploy Stamp** workflow for the first region.
3. If using platform ACR: assign `AcrPull` to the customer's kubelet identity on the platform ACR after first deploy.
4. Submit GPU quota requests on the customer subscription if `enableGpuPools = true` is needed.

### Adding a New Region

1. Create `infra/environments/{env}.{newRegionShort}.bicepparam` with the region's config.
2. Run the `Deploy Stamp` workflow with the customer ID and new region inputs.
3. The workflow creates the resource group and deploys all resources.

### CI/CD

- **GitHub Actions** with **OIDC federated credentials** (no stored secrets — uses `azure/login@v2` with `id-token: write`).
- **Nine workflows:**
  - **`onboard-customer.yml`** — Creates subscription, identity, RBAC, GitHub environments, manifest, and param files. Run once per customer.
  - **`deploy-platform.yml`** — Deploys shared platform infra (ACR, engine cache, monitoring, Platform AKS, DNS) to the operations subscription `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9`. Uses `azure/arm-deploy@v2`.
  - **`deploy-stamp.yml`** — Deploys a customer regional stamp (Validate → What-If → Approval Gate → Deploy). Uses `azure/arm-deploy@v2`.
  - **`build-api-server.yml`** — Lint, test, build API server Docker image, push to platform ACR, optional Helm deploy.
  - **`build-web.yml`** — Lint, build web Docker image, push to platform ACR, optional Helm deploy to Platform AKS. Triggers on `src/web/**` changes.
  - **`build-engines.yml`** — Build and push inference engine images (embeddings + TRT-LLM) to platform ACR. Supports stub mode for CI.
  - **`compile-engine.yml`** — Compile TRT-LLM engine for a specific model × GPU SKU. Registers result in engine cache.
  - **`deploy-model.yml`** — Deploy a model to a customer AKS cluster. Checks engine cache before compiling.
  - **`populate-cache.yml`** — Pre-compile engines for popular architectures (matrix: 5 arch × 2 GPU SKUs).
- **GitHub environments** are named `{customerId}-{env}` (e.g., `acme-prod`, `internal-dev`). Each environment has its own `AZURE_SUBSCRIPTION_ID` pointing to the customer's subscription. The `platform` environment targets the operations subscription.
- **Prod requires environment protection rules** — configure required reviewers in GitHub repo settings under Environments → `{customerId}-prod`.
- **Required GitHub secrets per customer environment:** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — all set automatically by the onboarding workflow.

### Platform Environment

The `platform` GitHub environment targets the operations subscription `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9` and is used by:
- `deploy-platform.yml` — deploying shared infra
- `build-api-server.yml` — pushing images to platform ACR
- `build-engines.yml` — pushing engine images to platform ACR
- `onboard-customer.yml` — creating customer subscriptions and identities

**All environments use a single SPN — `DevOptimum` (`291122ee-4f43-4b21-a337-c4d6e2382c8e`)** — with OIDC federated credentials per GitHub environment. The SPN has Contributor on both the operations and dev subscriptions.

| Secret | Description |
|---|---|
| `PLATFORM_AZURE_CLIENT_ID` | `291122ee-4f43-4b21-a337-c4d6e2382c8e` (DevOptimum SPN) |
| `PLATFORM_AZURE_TENANT_ID` | `7dd8cf8b-3a69-4cb3-96c9-0a9e63fe6127` |
| `PLATFORM_AZURE_SUBSCRIPTION_ID` | `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9` |
| `ONBOARDING_AZURE_CLIENT_ID` | `291122ee-4f43-4b21-a337-c4d6e2382c8e` (same SPN) |
| `ONBOARDING_AZURE_TENANT_ID` | `7dd8cf8b-3a69-4cb3-96c9-0a9e63fe6127` |
| `ONBOARDING_AZURE_SUBSCRIPTION_ID` | `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9` |
| `ONBOARDING_PAT` | GitHub PAT with `repo`, `admin:org` scopes (to create environments + set secrets) |

### OIDC Setup (Azure ↔ GitHub)

OIDC federated credentials are **created automatically** by the onboarding workflow. For each customer, the workflow:

1. Creates an App Registration in Entra ID (`sp-dai-{customerId}`).
2. Creates a Service Principal for the app.
3. Adds Federated Credentials for each GitHub environment (`repo:TheManInTheBox/DirectAI:environment:{customerId}-dev`, `...prod`).
4. Assigns `Contributor` + `User Access Administrator` on the customer's subscription.
5. Sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as GitHub environment secrets.

**No manual OIDC setup is needed unless you are bootstrapping the platform environment itself.**

#### Bootstrap (One-Time Platform Setup) — COMPLETED

All environments use a single existing SPN (`DevOptimum`) rather than three dedicated App Registrations. Federated credentials were added to the existing App Registration.

**SPN:** `DevOptimum`
- **Application (Client) ID:** `291122ee-4f43-4b21-a337-c4d6e2382c8e`
- **Object ID:** `c19a53f4-56e4-4d8e-b9fd-c643adcc3984`
- **SP Object ID:** `18a3e365-e61d-4242-97f1-087c17a0f527`
- **Tenant ID:** `7dd8cf8b-3a69-4cb3-96c9-0a9e63fe6127`

**Federated Credentials (OIDC):**

| Credential Name | GitHub Environment | Federated Subject |
|---|---|---|
| `directai-platform` | `platform` | `repo:TheManInTheBox/DirectAI:environment:platform` |
| `directai-internal-dev` | `internal-dev` | `repo:TheManInTheBox/DirectAI:environment:internal-dev` |
| `directai-internal-prod` | `internal-prod` | `repo:TheManInTheBox/DirectAI:environment:internal-prod` |

**RBAC (pre-existing):**
- Contributor on operations subscription `b03c9eb4-cddc-4987-9673-9ac44b9cc1d9`
- Contributor on dev subscription `0ae2be9a-f470-4dfe-b2e0-b7e9726acdfb`

**GitHub Environment Secrets:**

| Environment | `*_CLIENT_ID` | `*_TENANT_ID` | `*_SUBSCRIPTION_ID` |
|---|---|---|---|
| `platform` | `PLATFORM_AZURE_CLIENT_ID` / `ONBOARDING_AZURE_CLIENT_ID` | `PLATFORM_AZURE_TENANT_ID` / `ONBOARDING_AZURE_TENANT_ID` | `PLATFORM_AZURE_SUBSCRIPTION_ID` / `ONBOARDING_AZURE_SUBSCRIPTION_ID` → ops sub |
| `internal-dev` | `AZURE_CLIENT_ID` | `AZURE_TENANT_ID` | `AZURE_SUBSCRIPTION_ID` → dev sub |
| `internal-prod` | `AZURE_CLIENT_ID` | `AZURE_TENANT_ID` | *(not set — no prod subscription yet)* |

**Completed deployment steps:**

1. ✅ `deploy-platform.yml` run — ACR, Storage, Log Analytics, App Insights, DNS Zone, Platform AKS all deployed.
2. ✅ `vars.ACR_NAME` = `acrplatformdaiv7fgid`, `vars.ACR_LOGIN_SERVER` = `acrplatformdaiv7fgid.azurecr.io` set on the `platform` environment.
3. ✅ NS delegation configured at GoDaddy → Azure DNS nameservers (`ns1-02.azure-dns.com`, etc.).
4. ✅ Platform AKS: NGINX Ingress Controller, cert-manager v1.19, Let's Encrypt prod ClusterIssuer.
5. ✅ Web app live at `https://agilecloud.ai` — 2 replicas, TLS cert valid until June 2026.
6. ✅ Dev stamp deployed: `aks-dai-internal-dev-scus` (T4 GPU) with API server, embeddings backend (BGE-large), and LLM backend (Qwen 2.5 3B via vLLM).
7. ✅ DNS A records managed in Bicep: `agilecloud.ai` + `www.agilecloud.ai` → `4.153.165.222` (Platform AKS), `api.agilecloud.ai` → `48.192.177.54` (Dev AKS).
8. ✅ LLM inference live at `https://api.agilecloud.ai/v1/chat/completions` — streaming + non-streaming.

**Remaining manual steps:**

1. Add **required reviewers** to `internal-prod` GitHub environment (Settings → Environments).
2. Create a GitHub PAT with `repo` + `admin:org` scopes and set it as `ONBOARDING_PAT` secret on the `platform` environment.
3. Run `build-web.yml` end-to-end to validate the CI pipeline.
