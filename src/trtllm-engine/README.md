# DirectAI TRT-LLM Inference Engine

High-performance LLM inference server built on NVIDIA TensorRT-LLM. Serves OpenAI-compatible `/v1/chat/completions` with both streaming (SSE) and non-streaming modes.

This is a **backend engine** — it runs inside a GPU pod on AKS. The DirectAI API server proxies traffic to this engine.

## Architecture

```
Client → API Server → [this engine] → TRT-LLM → GPU
                         ↓
                    /v1/chat/completions
                    /v1/models
                    /healthz, /readyz
                    /metrics (Prometheus)
```

### Components

| Module | Purpose |
|---|---|
| `engine/config.py` | pydantic-settings config with `TRTLLM_` prefix |
| `engine/runner.py` | TRT-LLM HLAPI wrapper — deferred import, stub mode for dev |
| `engine/chat_format.py` | OpenAI ChatCompletion format conversion |
| `engine/metrics.py` | Prometheus metrics — latency, TTFT, token counts |
| `engine/main.py` | FastAPI app — endpoints, lifespan, SSE streaming |

### Key Design Decisions

- **Deferred TRT-LLM import**: `tensorrt_llm` is only available inside NVIDIA containers. The runner uses stub mode when the package isn't installed, so the codebase can be developed/tested without GPU hardware.
- **HLAPI, not low-level API**: Uses TRT-LLM's High-Level API (`LLM` class) which handles KV cache management, scheduling, and TP sharding internally.
- **Weights are NOT baked into images**: Engine artifacts and tokenizer files are mounted at `/models` at runtime from Azure Blob Storage / NVMe cache.
- **MPI for pipeline parallelism**: Multi-node PP uses `mpirun`. Single-node TP is handled internally by HLAPI.

## Supported Models

Any model that TRT-LLM can compile. Pre-compiled engine cache targets:

| Architecture | Example Models | TP Degree |
|---|---|---|
| Llama 3.x | Llama-3.1-8B, 70B, 405B | 1, 2, 4, 8 |
| Qwen 2.x | Qwen2.5-7B, 72B | 1, 2, 8 |
| Mistral / Mixtral | Mistral-7B, Mixtral-8x7B | 1, 2 |
| DeepSeek V3 | DeepSeek-V3-671B | 8 |
| Whisper | whisper-large-v3 | 1 |

## Configuration

All settings use the `TRTLLM_` environment variable prefix.

| Variable | Default | Description |
|---|---|---|
| `TRTLLM_HOST` | `0.0.0.0` | Bind address |
| `TRTLLM_PORT` | `8001` | Bind port |
| `TRTLLM_ENGINE_DIR` | `/models/engine` | Path to compiled TRT-LLM engine |
| `TRTLLM_TOKENIZER_DIR` | `/models/tokenizer` | Path to HuggingFace tokenizer |
| `TRTLLM_MODEL_NAME` | `llama-3.1-70b-instruct` | Model name reported in API responses |
| `TRTLLM_MAX_BATCH_SIZE` | `64` | Maximum concurrent requests |
| `TRTLLM_MAX_INPUT_LEN` | `4096` | Max input prompt tokens |
| `TRTLLM_MAX_OUTPUT_LEN` | `4096` | Max output tokens per request |
| `TRTLLM_TP_SIZE` | `1` | Tensor parallelism degree |
| `TRTLLM_PP_SIZE` | `1` | Pipeline parallelism degree (Phase 2) |
| `TRTLLM_KV_CACHE_FREE_GPU_MEM_FRACTION` | `0.85` | GPU memory fraction for KV cache |
| `TRTLLM_ENABLE_CHUNKED_CONTEXT` | `true` | Enable chunked context for long sequences |
| `TRTLLM_LOG_LEVEL` | `info` | Log level |

## Usage

### Local Development (Stub Mode)

Without TRT-LLM installed, the engine runs in stub mode — all generation calls return placeholder responses. Useful for testing the HTTP layer and API format.

```bash
cd src/trtllm-engine
pip install -e "."

# Set a tokenizer path (any HuggingFace tokenizer)
export TRTLLM_TOKENIZER_DIR=meta-llama/Llama-3.1-8B-Instruct
export TRTLLM_MODEL_NAME=llama-3.1-8b-instruct

python -m engine.main
```

### Docker Build

```bash
# Without TRT-LLM (stub mode for CI/testing)
docker build --build-arg INSTALL_TRTLLM=false -t directai-trtllm-engine:stub .

# With TRT-LLM (production)
docker build -t directai-trtllm-engine:latest .
```

### Docker Run (Production)

```bash
docker run --gpus all \
  -v /path/to/engine:/models/engine \
  -v /path/to/tokenizer:/models/tokenizer \
  -e TRTLLM_MODEL_NAME=llama-3.1-70b-instruct \
  -e TRTLLM_TP_SIZE=8 \
  -e TRTLLM_KV_CACHE_FREE_GPU_MEM_FRACTION=0.90 \
  -p 8001:8001 \
  directai-trtllm-engine:latest
```

### API Examples

**Non-streaming:**
```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

**Streaming (SSE):**
```bash
curl -N http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true,
    "max_tokens": 100
  }'
```

## Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `directai_llm_inflight_requests` | Gauge | Requests currently generating |
| `directai_llm_requests_total` | Counter | Total requests by `{status, stream}` |
| `directai_llm_request_duration_seconds` | Histogram | E2E request latency |
| `directai_llm_time_to_first_token_seconds` | Histogram | Time to first token (TTFT) |
| `directai_llm_tokens_generated_total` | Counter | Total output tokens |
| `directai_llm_prompt_tokens_total` | Counter | Total input tokens |

## Performance Targets

| Metric | Target (A100 80GB) | Target (H100 80GB) |
|---|---|---|
| TTFT (8B model) | < 50ms | < 30ms |
| TTFT (70B model, TP=8) | < 200ms | < 100ms |
| Token throughput (8B) | > 2000 tok/s | > 4000 tok/s |
| Token throughput (70B, TP=8) | > 800 tok/s | > 1500 tok/s |
| P99 latency (256 output tokens) | < 5s | < 3s |

## Engine Compilation

TRT-LLM engines must be compiled ahead of time for each model × GPU SKU combination. See the engine cache strategy in the project README.

```bash
# Example: compile Llama-3.1-8B for A100
python -m tensorrt_llm.commands.build \
  --model_dir /weights/llama-3.1-8b \
  --output_dir /engines/llama-3.1-8b-a100 \
  --dtype float16 \
  --tp_size 1 \
  --max_batch_size 64 \
  --max_input_len 4096 \
  --max_seq_len 8192 \
  --gemm_plugin float16 \
  --gpt_attention_plugin float16
```

Engine cache key format: `{architecture}_{params}_{quant}_{gpu_sku}_{trtllm_version}`
