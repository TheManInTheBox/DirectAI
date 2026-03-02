"""
FastAPI application — OpenAI-compatible embeddings inference server.

Endpoints:
  POST /v1/embeddings  — OpenAI-compatible embedding endpoint
  GET  /v1/models      — List available models
  GET  /healthz        — Liveness probe
  GET  /readyz         — Readiness probe (model loaded)
  GET  /metrics        — Prometheus metrics
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import Response

from engine.batcher import DynamicBatcher
from engine.config import get_settings
from engine.metrics import (
    BATCH_SIZE,
    INFLIGHT_REQUESTS,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
    TOKENS_TOTAL,
    metrics_content_type,
    metrics_response_body,
)
from engine.model import EmbeddingModel

logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )

    # Load model
    model = EmbeddingModel(
        model_path=settings.model_path,
        tokenizer_path=settings.tokenizer_path,
        max_seq_length=settings.max_seq_length,
        normalize=settings.normalize_embeddings,
        execution_provider=settings.execution_provider,
        num_threads=settings.num_threads,
    )
    model.load()
    app.state.model = model

    # Start batcher
    batcher = DynamicBatcher(
        model,
        max_batch_size=settings.max_batch_size,
        batch_timeout_ms=settings.batch_timeout_ms,
    )
    await batcher.start()
    app.state.batcher = batcher
    app.state.model_name = settings.model_name

    logger.info("Embeddings engine ready — model=%s, dim=%d", settings.model_name, model.embedding_dim)

    yield

    await batcher.stop()
    logger.info("Embeddings engine shut down.")


app = FastAPI(title="DirectAI Embeddings Engine", version="0.1.0", lifespan=lifespan)


# ── Schemas ─────────────────────────────────────────────────────────────


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    encoding_format: str | None = "float"
    dimensions: int | None = None
    user: str | None = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default=0)
    owned_by: str = "directai"


class ModelList(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


# ── Endpoints ───────────────────────────────────────────────────────────


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embedding(body: EmbeddingRequest, request: Request):
    """OpenAI-compatible embeddings endpoint with dynamic batching."""
    batcher: DynamicBatcher = request.app.state.batcher
    model_name: str = request.app.state.model_name

    t0 = time.monotonic()
    INFLIGHT_REQUESTS.inc()

    try:
        # Normalize input to list
        texts = body.input if isinstance(body.input, list) else [body.input]

        if not texts:
            raise HTTPException(status_code=400, detail="Input must not be empty.")

        if len(texts) > get_settings().max_batch_size:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size {len(texts)} exceeds maximum {get_settings().max_batch_size}.",
            )

        BATCH_SIZE.observe(len(texts))

        # Submit to dynamic batcher
        embeddings = await batcher.submit_batch(texts)

        # Estimate token count (rough — actual tokenization happens in model)
        # Using ~1.3 tokens per word as rough heuristic for the response
        est_tokens = sum(len(t.split()) for t in texts)
        TOKENS_TOTAL.inc(est_tokens)

        # Build response
        data = [
            EmbeddingData(index=i, embedding=emb.tolist())
            for i, emb in enumerate(embeddings)
        ]

        duration = time.monotonic() - t0
        REQUEST_DURATION.observe(duration)
        REQUESTS_TOTAL.labels(status="ok").inc()

        return EmbeddingResponse(
            data=data,
            model=model_name,
            usage=EmbeddingUsage(prompt_tokens=est_tokens, total_tokens=est_tokens),
        )

    except HTTPException:
        REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except Exception:
        REQUESTS_TOTAL.labels(status="error").inc()
        logger.exception("Embedding inference failed")
        raise HTTPException(status_code=500, detail="Inference failed.")
    finally:
        INFLIGHT_REQUESTS.dec()


@app.get("/v1/models", response_model=ModelList)
async def list_models(request: Request):
    model_name = request.app.state.model_name
    return ModelList(data=[ModelInfo(id=model_name)])


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    model: EmbeddingModel = request.app.state.model
    batcher: DynamicBatcher = request.app.state.batcher
    if not model.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    if not batcher.is_healthy:
        raise HTTPException(status_code=503, detail="Batcher loop not running.")
    return {"status": "ready", "model": request.app.state.model_name}


@app.get("/metrics")
async def metrics():
    return Response(
        content=metrics_response_body(),
        media_type=metrics_content_type(),
    )
