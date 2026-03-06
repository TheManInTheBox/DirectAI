"""
DirectAI API Server — Application entrypoint.

A lightweight OpenAI-compatible routing layer that proxies inference
requests to backend model pods running TensorRT-LLM / ONNX Runtime.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.audit import AuditMiddleware
from app.config import get_settings
from app.metrics import metrics_content_type, metrics_response_body
from app.middleware import CorrelationIdMiddleware, RateLimitMiddleware, RequestLoggingMiddleware
from app.models import ModelRepository
from app.routes import (
    audio_router,
    chat_router,
    embeddings_router,
    models_router,
    native_deployments_router,
    native_engine_cache_router,
    native_models_router,
    native_system_router,
)
from app.routing import BackendClient, BackendHealthMonitor, ModelRegistry
from app.telemetry import configure_tracing, shutdown_tracing


class _JSONFormatter(logging.Formatter):
    """Structured JSON log formatter that serializes `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra fields set via logger.info("...", extra={...})
        for key in ("method", "path", "status_code", "duration_ms", "request_id"):
            val = getattr(record, key, None)
            if val is not None:
                log[key] = val
        return json.dumps(log, default=str)


def _configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    _configure_logging()
    logger = logging.getLogger(__name__)

    # Record startup time for /api/v1/health uptime calculation.
    from app.routes.native_system import _set_startup_time
    _set_startup_time()

    settings = get_settings()

    # ── Tracing (OpenTelemetry) ─────────────────────────────────────
    if settings.otel_enabled:
        configure_tracing(
            appinsights_connection_string=settings.appinsights_connection_string,
            otlp_endpoint=settings.otlp_endpoint,
            sample_rate=settings.otel_sample_rate,
        )

    # ── PostgreSQL key store (API key validation + usage metering) ──
    from app.auth.key_store import PostgresKeyStore
    key_store = PostgresKeyStore(
        database_url=settings.database_url,
        cache_ttl=settings.key_cache_ttl,
        spend_cache_ttl=settings.spend_cache_ttl,
    )
    await key_store.startup()
    app.state.key_store = key_store

    # ── Audit writer (compliance logging) ───────────────────────
    from app.audit.config import AuditConfig
    from app.audit.writer import AuditWriter
    audit_config = AuditConfig(
        enabled=settings.audit_enabled,
        pg_enabled=settings.audit_pg_enabled,
        pg_retention_days=settings.audit_pg_retention_days,
        blob_enabled=settings.audit_blob_enabled,
        storage_account=settings.audit_storage_account,
        storage_container=settings.audit_storage_container,
        retention_days=settings.audit_retention_days,
        queue_size=settings.audit_queue_size,
        flush_interval=settings.audit_flush_interval,
        batch_size=settings.audit_batch_size,
    )
    audit_writer = AuditWriter(
        config=audit_config,
        pg_pool=key_store._pool if key_store.enabled else None,
    )
    await audit_writer.start()
    app.state.audit_writer = audit_writer

    # ── Stripe usage reporter (hybrid billing — metered per-token) ──
    from app.billing import StripeUsageReporter
    usage_reporter = StripeUsageReporter(
        stripe_secret_key=settings.stripe_secret_key,
        flush_interval=settings.usage_report_interval,
    )
    await usage_reporter.start()
    app.state.usage_reporter = usage_reporter

    # ── Model registry ──────────────────────────────────────────────
    registry = ModelRegistry.from_directory(settings.model_config_dir)
    app.state.model_registry = registry
    logger.info("Loaded %d models from %s", len(registry), settings.model_config_dir)
    # ── Model repository (SQLite) ─────────────────────────
    repository = ModelRepository(settings.database_path)
    await repository.startup()
    app.state.model_repository = repository
    logger.info("Model repository ready (%s)", settings.database_path)
    # ── Backend HTTP client ─────────────────────────────────────────
    backend = BackendClient()
    await backend.startup()
    app.state.backend_client = backend

    # ── Backend health monitor ──────────────────────────────────────
    monitor = BackendHealthMonitor()
    backend_urls = {
        spec.name: spec.backend_url
        for spec in registry.list_models()
    }
    if backend_urls:
        await monitor.start(backend_urls)
    app.state.health_monitor = monitor

    yield

    # ── Shutdown ────────────────────────────────────────────────────
    await monitor.stop()
    await audit_writer.stop()
    await usage_reporter.stop()
    await repository.shutdown()
    await backend.shutdown()
    await key_store.shutdown()
    shutdown_tracing()
    logger.info("API server shut down.")


app = FastAPI(
    title="DirectAI",
    description="High-performance AI inference API — OpenAI-compatible.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost first) ─────────────────────
# Stack (outermost → innermost):
#   CorrelationIdMiddleware → RateLimitMiddleware → AuditMiddleware → RequestLoggingMiddleware
# Audit sits inside rate-limiting so rejected requests aren't audited,
# but outside logging so audit has the final status code.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuditMiddleware)
_settings = get_settings()
app.add_middleware(
    RateLimitMiddleware,
    rpm=_settings.rate_limit_rpm,
    tpm=_settings.rate_limit_tpm,
    max_buckets=_settings.rate_limit_max_buckets,
)
app.add_middleware(CorrelationIdMiddleware)

# ── Routes ──────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(embeddings_router)
app.include_router(audio_router)
app.include_router(models_router)
app.include_router(native_models_router)
app.include_router(native_deployments_router)
app.include_router(native_engine_cache_router)
app.include_router(native_system_router)


# ── Health probes ───────────────────────────────────────────────────


@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Liveness probe — always returns 200 if the process is alive."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz(request: Request):
    """Readiness probe — 200 if models loaded AND at least one backend healthy."""
    registry = request.app.state.model_registry
    if len(registry) == 0:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "No models loaded."},
        )
    # Backend health is informational — do NOT gate readyz on it.
    # If readyz returns 503 for unhealthy backends, K8s removes the pod
    # from Service endpoints and clients get connection refused instead of
    # a useful 503+Retry-After from route handlers.
    monitor = getattr(request.app.state, "health_monitor", None)
    backend_health = monitor.summary() if monitor else {}
    return {"status": "ready", "models": len(registry), "backends": backend_health}


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
