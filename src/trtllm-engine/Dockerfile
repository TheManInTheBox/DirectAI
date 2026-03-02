# ─────────────────────────────────────────────────────────────
# DirectAI TRT-LLM Inference Engine
# ─────────────────────────────────────────────────────────────
# Multi-stage build:
#   1. Runtime: NVIDIA TRT-LLM base image + FastAPI server
#
# Model weights and compiled engines are NOT baked into the image.
# They are mounted at runtime from Azure Blob / NVMe cache.
# ─────────────────────────────────────────────────────────────

# ── TRT-LLM Base ────────────────────────────────────────────
# Production: use the pre-built NVIDIA TRT-LLM container.
# CI/stub mode: use a lightweight CUDA base without tensorrt_llm.
#   Build with: docker build --build-arg USE_STUB=true .
ARG TRTLLM_VERSION=0.16.0
ARG USE_STUB=false

# ---- Production base: full TRT-LLM runtime ----
FROM nvcr.io/nvidia/tensorrt-llm/release:${TRTLLM_VERSION} AS base-prod

# ---- CI/stub base: no TRT-LLM, runs in stub mode ----
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS base-stub
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    curl \
    openmpi-bin \
    libopenmpi-dev \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Select base ----
# Docker doesn't support conditional FROM directly, so we use the
# build stage target approach: build with --target runtime for prod,
# or --build-arg USE_STUB=true && --target runtime for CI.
FROM base-prod AS base-false
FROM base-stub AS base-true
FROM base-${USE_STUB} AS base

# ── App layer ───────────────────────────────────────────────
FROM base AS runtime

WORKDIR /app

# Install Python deps (without tensorrt_llm — already in base)
COPY pyproject.toml .
COPY engine/ engine/
RUN pip3 install --no-cache-dir .

# ── Model mount points ──────────────────────────────────────
# Engine artifacts and tokenizer are mounted here at runtime.
# Do NOT bake weights into the image.
RUN mkdir -p /models/engine /models/tokenizer

# ── Runtime config ──────────────────────────────────────────
ENV TRTLLM_HOST=0.0.0.0
ENV TRTLLM_PORT=8001
ENV TRTLLM_LOG_LEVEL=info

# MPI settings for multi-GPU tensor parallelism
# SECURITY: MPI requires root for shared-memory transport (vader btl).
# Running as non-root breaks multi-GPU tensor parallelism. Mitigated by:
#   - Read-only root filesystem in K8s securityContext
#   - No shell access in production (no SSH, no kubectl exec)
#   - Network policies restrict pod-to-pod traffic
ENV OMPI_MCA_btl_vader_single_copy_mechanism=none
ENV OMPI_ALLOW_RUN_AS_ROOT=1
ENV OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

# NVIDIA runtime
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

EXPOSE 8001

# Health check — liveness probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/healthz || exit 1

# ── Entrypoint ──────────────────────────────────────────────
# For single-GPU or single-node multi-GPU (TP within one node):
#   Just run uvicorn directly.
# For multi-node (PP across nodes):
#   Use mpirun -n $WORLD_SIZE python -m engine.main
#
# The entrypoint script handles both cases.
COPY <<'EOF' /app/entrypoint.sh
#!/bin/bash
set -euo pipefail

TP=${TRTLLM_TP_SIZE:-1}
PP=${TRTLLM_PP_SIZE:-1}
WORLD_SIZE=$((TP * PP))

if [ "$WORLD_SIZE" -gt 1 ] && [ "$PP" -gt 1 ]; then
    echo "Starting with mpirun (TP=$TP, PP=$PP, WORLD_SIZE=$WORLD_SIZE)"
    exec mpirun --allow-run-as-root -n "$WORLD_SIZE" \
        python -m engine.main
else
    echo "Starting single-process (TP=$TP via HLAPI internal sharding)"
    exec python -m engine.main
fi
EOF

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
