# ============================================================================
# DirectAI API Server
#
# Lightweight OpenAI-compatible routing layer. Does NOT run inference —
# proxies requests to backend model pods (TensorRT-LLM, ONNX Runtime).
# ============================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Dependencies + Application ──────────────────────────────────────
COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir . \
    && rm -rf /root/.cache/pip

# ── Model configs are mounted at runtime (ConfigMap or volume) ──────
# Default path: /app/models — override via DIRECTAI_MODEL_CONFIG_DIR
RUN mkdir -p /app/models

# ── Non-root user ───────────────────────────────────────────────────
RUN adduser --system --no-create-home appuser \
    && chown -R appuser:nogroup /app
USER appuser

EXPOSE 8000

# ── Entrypoint ──────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
