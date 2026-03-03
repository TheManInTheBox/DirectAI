"""
OpenTelemetry tracing setup for the DirectAI API server.

Provides:
  - TracerProvider with Azure Monitor + optional OTLP exporters
  - FastAPI and httpx auto-instrumentation
  - W3C TraceContext propagation to backend engines
  - ``get_tracer()`` accessor for manual spans
  - Graceful no-op when tracing is disabled (``DIRECTAI_OTEL_ENABLED=false``)

Design decisions:
  - The module is *imported* at startup but only *activates* when
    ``configure_tracing()`` is called — this avoids side effects on import.
  - When disabled, ``get_tracer()`` returns the global NoOp tracer so
    callers never need to guard ``if tracing_enabled``.
  - Azure Monitor exporter only initialises when a connection string is
    provided.  In local dev you can run Jaeger + OTLP instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    TraceIdRatioBased,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export import SpanExporter

logger = logging.getLogger(__name__)

# ── Module state ───────────────────────────────────────────────────
_provider: TracerProvider | None = None
_TRACER_NAME = "directai.api-server"


def configure_tracing(
    *,
    service_name: str = "directai-api-server",
    service_version: str = "0.1.0",
    appinsights_connection_string: str = "",
    otlp_endpoint: str = "",
    sample_rate: float = 1.0,
) -> TracerProvider | None:
    """Initialise the global TracerProvider and auto-instrumentation.

    Returns the provider (for shutdown) or ``None`` when tracing is
    disabled (no exporters configured).
    """
    global _provider  # noqa: PLW0603

    exporters: list[SpanExporter] = []

    # ── Azure Monitor exporter ──────────────────────────────────
    if appinsights_connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            exporters.append(
                AzureMonitorTraceExporter(connection_string=appinsights_connection_string)
            )
            logger.info("Azure Monitor trace exporter configured.")
        except Exception:
            logger.exception("Failed to initialise Azure Monitor exporter — traces will be lost.")

    # ── OTLP exporter (local dev: Jaeger / Zipkin / Aspire) ─────
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporters.append(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
            logger.info("OTLP trace exporter configured → %s", otlp_endpoint)
        except Exception:
            logger.exception("Failed to initialise OTLP exporter.")

    if not exporters:
        logger.info("No trace exporters configured — tracing disabled (NoOp).")
        return None

    # ── Resource attributes ─────────────────────────────────────
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
        }
    )

    # ── Sampler ─────────────────────────────────────────────────
    sampler = ALWAYS_ON if sample_rate >= 1.0 else TraceIdRatioBased(sample_rate)

    provider = TracerProvider(resource=resource, sampler=sampler)

    for exporter in exporters:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # ── W3C TraceContext propagation (traceparent / tracestate) ──
    set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))

    # ── Auto-instrument FastAPI ─────────────────────────────────
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument(
            tracer_provider=provider,
            excluded_urls="healthz,readyz,metrics",
        )
        logger.info("FastAPI auto-instrumentation enabled.")
    except Exception:
        logger.exception("FastAPI instrumentation failed.")

    # ── Auto-instrument httpx (backend proxy client) ────────────
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        logger.info("httpx auto-instrumentation enabled.")
    except Exception:
        logger.exception("httpx instrumentation failed.")

    _provider = provider
    logger.info(
        "Tracing configured: %d exporter(s), sample_rate=%.2f",
        len(exporters),
        sample_rate,
    )
    return provider


def shutdown_tracing() -> None:
    """Flush pending spans and shut down the TracerProvider."""
    global _provider  # noqa: PLW0603
    if _provider is not None:
        _provider.shutdown()
        logger.info("TracerProvider shut down — all spans flushed.")
        _provider = None


def get_tracer() -> trace.Tracer:
    """Return a tracer scoped to the API server.

    Safe to call whether tracing is enabled or not — returns the
    global NoOp tracer when no provider is configured.
    """
    return trace.get_tracer(_TRACER_NAME)
