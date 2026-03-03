"""
Prometheus metrics for the DirectAI API server.

Exposes:
  - directai_backend_inflight_requests  (Gauge, per model)   — KEDA scaling trigger
  - directai_requests_total             (Counter, per model/method/status)
  - directai_request_duration_seconds   (Histogram, per model/method)

The /metrics endpoint is mounted directly on the FastAPI app.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── Dedicated registry (avoids default process metrics noise) ──────

REGISTRY = CollectorRegistry()

# ── Metrics ────────────────────────────────────────────────────────

INFLIGHT_REQUESTS = Gauge(
    "directai_backend_inflight_requests",
    "Number of inflight requests currently being proxied to a backend.",
    ["model"],
    registry=REGISTRY,
)

REQUESTS_TOTAL = Counter(
    "directai_requests_total",
    "Total number of inference requests.",
    ["model", "method", "status"],
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "directai_request_duration_seconds",
    "Latency of proxied inference requests in seconds.",
    ["model", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
    registry=REGISTRY,
)


# ── Helpers ────────────────────────────────────────────────────────


@contextmanager
def track_request(model: str, method: str) -> Generator[None, None, None]:
    """
    Context manager that tracks inflight count, latency, and total count
    for a single proxied request.

    Usage:
        with track_request("llama-3.1-70b", "chat"):
            response = await backend.post_json(...)
    """
    INFLIGHT_REQUESTS.labels(model=model).inc()
    timer = REQUEST_DURATION.labels(model=model, method=method).time()
    timer.__enter__()
    status = "error"
    try:
        yield
        status = "ok"
    except Exception:
        status = "error"
        raise
    finally:
        timer.__exit__(None, None, None)
        INFLIGHT_REQUESTS.labels(model=model).dec()
        REQUESTS_TOTAL.labels(model=model, method=method, status=status).inc()


def metrics_response_body() -> bytes:
    """Serialize all metrics in Prometheus text format."""
    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
