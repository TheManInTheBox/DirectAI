# ============================================================================
# DirectAI Embeddings Engine — Production GPU Container
# ============================================================================
# Multi-stage build:
#   1. Export stage — convert HuggingFace model to ONNX (build-time)
#   2. Runtime stage — slim ONNX Runtime GPU image
#
# Build args:
#   MODEL_ID    — HuggingFace model ID (default: BAAI/bge-large-en-v1.5)
#   MODEL_NAME  — Name exposed via /v1/models (default: bge-large-en-v1.5)
#
# The model is NOT baked into the image by default. Mount weights at /models
# or set EMBED_MODEL_PATH / EMBED_TOKENIZER_PATH.
#
# To bake a model into the image for faster cold starts:
#   docker build --build-arg BAKE_MODEL=1 --build-arg MODEL_ID=BAAI/bge-large-en-v1.5 .
# ============================================================================

# ── Stage 1: Export (optional — only when BAKE_MODEL=1) ─────────────────
# Uses engine/export.py for the HuggingFace → ONNX conversion.
# Torch CPU-only keeps the exporter stage small.

FROM python:3.11-slim AS exporter

ARG BAKE_MODEL=0
ARG MODEL_ID=BAAI/bge-large-en-v1.5

COPY engine/export.py /tmp/export_model.py

RUN if [ "$BAKE_MODEL" = "1" ]; then \
        pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
        && pip install --no-cache-dir "optimum[onnxruntime]" transformers \
        && python /tmp/export_model.py \
             --model-id "$MODEL_ID" \
             --output-dir /export \
             --no-fp16 \
        && echo "Export complete"; \
    else \
        mkdir -p /export && echo 'Skipping model export — mount weights at /models'; \
    fi


# ── Stage 2: Runtime ────────────────────────────────────────────────────

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS runtime

ARG MODEL_NAME=bge-large-en-v1.5
ARG BAKE_MODEL=0

# System deps: Python 3.11 (via deadsnakes PPA — Ubuntu 22.04 ships 3.10) + ONNX Runtime GPU needs
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3.11-distutils \
        libgomp1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && python3.11 -m ensurepip --upgrade \
    && python3.11 -m pip install --no-cache-dir --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps + application code
COPY pyproject.toml .
COPY engine/ engine/
RUN pip3 install --no-cache-dir . \
    && rm -rf /root/.cache/pip

# Copy baked model (if exported)
COPY --from=exporter /export/ /models/

# ── Environment defaults ────────────────────────────────────────────────
ENV EMBED_HOST=0.0.0.0 \
    EMBED_PORT=8001 \
    EMBED_MODEL_PATH=/models/model.onnx \
    EMBED_TOKENIZER_PATH=/models/tokenizer.json \
    EMBED_MODEL_NAME=${MODEL_NAME} \
    EMBED_MAX_SEQ_LENGTH=512 \
    EMBED_MAX_BATCH_SIZE=256 \
    EMBED_BATCH_TIMEOUT_MS=5.0 \
    EMBED_EXECUTION_PROVIDER=CUDAExecutionProvider \
    EMBED_NORMALIZE_EMBEDDINGS=true \
    EMBED_LOG_LEVEL=info

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/healthz')"

# ── Non-root user ───────────────────────────────────────────────────
RUN adduser --system --no-create-home appuser \
    && chown -R appuser:nogroup /app /models
USER appuser

# Run with single worker for GPU-bound workload
CMD ["python3", "-m", "uvicorn", "engine.main:app", \
     "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "1", \
     "--log-level", "info"]
