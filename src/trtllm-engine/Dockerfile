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
# Pin to a specific TRT-LLM release for reproducibility.
# This image includes CUDA, cuDNN, TensorRT, and tensorrt_llm.
ARG TRTLLM_VERSION=0.16.0
ARG BASE_IMAGE=nvidia/cuda:12.8.0-devel-ubuntu22.04

FROM ${BASE_IMAGE} AS base

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# ── System deps ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    curl \
    git \
    openmpi-bin \
    libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# ── Install TRT-LLM ────────────────────────────────────────
# In production, use the pre-built NVIDIA TRT-LLM container:
#   FROM nvcr.io/nvidia/tensorrt-llm:${TRTLLM_VERSION}
# For build flexibility, we install from PyPI here.
# When TRT-LLM wheels are not available (CI, non-GPU), the
# engine runs in stub mode.
ARG INSTALL_TRTLLM=true
RUN if [ "$INSTALL_TRTLLM" = "true" ]; then \
        pip3 install --no-cache-dir \
            tensorrt_llm==${TRTLLM_VERSION} \
            --extra-index-url https://pypi.nvidia.com; \
    fi

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
