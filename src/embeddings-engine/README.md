# DirectAI Embeddings Engine

High-throughput ONNX Runtime embedding inference server with dynamic batching.

## Architecture

```
Client → API Server → [this server] → ONNX Runtime (GPU)
                         ↑
                  Dynamic Batcher
                  (collects requests into GPU-efficient batches)
```

## Features

- **OpenAI-compatible** `/v1/embeddings` endpoint — drop-in backend for the DirectAI API server
- **Dynamic batching** — collects individual requests into GPU-efficient batches (configurable max size + timeout)
- **ONNX Runtime GPU** — optimized inference with CUDA execution provider
- **FP16 support** — optional half-precision conversion for 2x throughput
- **HuggingFace tokenizers** — fast Rust tokenizer for zero-overhead tokenization
- **Mean pooling + L2 normalization** — standard embedding post-processing
- **Prometheus metrics** — inflight gauge, request counter, latency histogram, batch size histogram
- **Health probes** — `/healthz` (liveness) and `/readyz` (model loaded)

## Supported Models

Any HuggingFace transformer model that outputs `last_hidden_state`:

| Model | Params | Dim | Notes |
|---|---|---|---|
| BAAI/bge-large-en-v1.5 | 335M | 1024 | Primary production model |
| BAAI/bge-base-en-v1.5 | 109M | 768 | Smaller, faster |
| nomic-ai/nomic-embed-text-v1.5 | 137M | 768 | Good quality/speed ratio |
| intfloat/e5-large-v2 | 335M | 1024 | Alternative |
| thenlper/gte-large | 335M | 1024 | Alternative |

## Usage

### Export a Model to ONNX

```bash
pip install optimum[onnxruntime-gpu] transformers torch
python -m engine.export --model-id BAAI/bge-large-en-v1.5 --output-dir ./models
```

### Run Locally (CPU)

```bash
cd src/embeddings-engine
pip install -e ".[cpu,dev]"

EMBED_MODEL_PATH=./models/model.onnx \
EMBED_TOKENIZER_PATH=./models/tokenizer.json \
EMBED_EXECUTION_PROVIDER=CPUExecutionProvider \
python -m uvicorn engine.main:app --port 8001
```

### Run with Docker (GPU)

```bash
# Without baked model (mount weights):
docker build -t directai/onnx-embeddings:0.1.0 .
docker run --gpus all -p 8001:8001 -v /path/to/models:/models directai/onnx-embeddings:0.1.0

# With baked model:
docker build --build-arg BAKE_MODEL=1 --build-arg MODEL_ID=BAAI/bge-large-en-v1.5 \
    -t directai/onnx-embeddings:0.1.0-bge .
```

### Test

```bash
curl http://localhost:8001/v1/embeddings \
    -H "Content-Type: application/json" \
    -d '{"model": "bge-large-en-v1.5", "input": "Hello world"}'
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EMBED_HOST` | `0.0.0.0` | Bind address |
| `EMBED_PORT` | `8001` | Bind port |
| `EMBED_MODEL_PATH` | `/models/model.onnx` | Path to ONNX model file |
| `EMBED_TOKENIZER_PATH` | `/models/tokenizer.json` | Path to tokenizer file |
| `EMBED_MODEL_NAME` | `bge-large-en-v1.5` | Model name in /v1/models |
| `EMBED_MAX_SEQ_LENGTH` | `512` | Max tokens per input text |
| `EMBED_MAX_BATCH_SIZE` | `256` | Max texts per GPU batch |
| `EMBED_BATCH_TIMEOUT_MS` | `5.0` | Max wait to fill a batch (ms) |
| `EMBED_EXECUTION_PROVIDER` | `CUDAExecutionProvider` | ONNX Runtime provider |
| `EMBED_NORMALIZE_EMBEDDINGS` | `true` | L2-normalize output vectors |
| `EMBED_NUM_THREADS` | `4` | ONNX Runtime intra-op threads |
| `EMBED_LOG_LEVEL` | `info` | Log level |

## Performance

Benchmarks on A10G (single GPU, BGE-large, FP16, batch_size=128):

| Metric | Value |
|---|---|
| Throughput | ~3,000 texts/sec |
| P50 latency (single text) | ~3ms |
| P99 latency (128-text batch) | ~45ms |
| GPU memory | ~2.5 GB |

> Numbers are targets — actual benchmarks pending production deployment.
