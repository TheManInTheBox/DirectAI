"""
DirectAI API Server — Application entrypoint.

A lightweight OpenAI-compatible routing layer that proxies inference
requests to backend model pods running TensorRT-LLM / ONNX Runtime.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.config import get_settings
from app.metrics import metrics_content_type, metrics_response_body
from app.middleware import CorrelationIdMiddleware, RequestLoggingMiddleware
from app.routing import BackendClient, ModelRegistry
from app.routes import audio_router, chat_router, embeddings_router, models_router


def _configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        stream=sys.stdout,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    _configure_logging()
    logger = logging.getLogger(__name__)

    settings = get_settings()

    # ── Model registry ──────────────────────────────────────────────
    registry = ModelRegistry.from_directory(settings.model_config_dir)
    app.state.model_registry = registry
    logger.info("Loaded %d models from %s", len(registry), settings.model_config_dir)

    # ── Backend HTTP client ─────────────────────────────────────────
    backend = BackendClient()
    await backend.startup()
    app.state.backend_client = backend

    yield

    # ── Shutdown ────────────────────────────────────────────────────
    await backend.shutdown()
    logger.info("API server shut down.")


app = FastAPI(
    title="DirectAI",
    description="High-performance AI inference API — OpenAI-compatible.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost first) ─────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# ── Routes ──────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(embeddings_router)
app.include_router(audio_router)
app.include_router(models_router)


# ── Health probes ───────────────────────────────────────────────────


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Liveness probe — always returns 200 if the process is alive."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz(request: Request):
    """Readiness probe — returns 200 if the model registry is loaded."""
    registry = request.app.state.model_registry
    if len(registry) == 0:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "No models loaded."},
        )
    return {"status": "ready", "models": len(registry)}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint — scraped by Prometheus server."""
    return Response(
        content=metrics_response_body(),
        media_type=metrics_content_type(),
    )


# ── Global error handler ───────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger = logging.getLogger(__name__)
    request_id = getattr(request.state, "request_id", "-")
    logger.error("Unhandled exception [%s]: %s", request_id, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error.",
                "type": "server_error",
                "code": "internal_error",
            }
        },
        headers={"X-Request-ID": request_id},
    )
