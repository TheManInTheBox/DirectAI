"""
Prometheus metrics for the embeddings inference engine.

Metrics exposed:
  - directai_embed_inflight_requests: Gauge of requests currently being processed
  - directai_embed_requests_total: Counter of completed requests (status label)
  - directai_embed_request_duration_seconds: Histogram of E2E request latency
  - directai_embed_batch_size: Histogram of batch sizes dispatched
  - directai_embed_tokens_processed_total: Counter of total tokens tokenized
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Dedicated registry — no default process/platform metrics
REGISTRY = CollectorRegistry()

INFLIGHT_REQUESTS = Gauge(
    "directai_embed_inflight_requests",
    "Number of embedding requests currently in-flight.",
    registry=REGISTRY,
)

REQUESTS_TOTAL = Counter(
    "directai_embed_requests_total",
    "Total embedding requests processed.",
    ["status"],  # ok, error
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "directai_embed_request_duration_seconds",
    "End-to-end embedding request latency in seconds.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

BATCH_SIZE = Histogram(
    "directai_embed_batch_size",
    "Number of texts per inference batch.",
    buckets=(1, 2, 4, 8, 16, 32, 64, 128, 256, 512),
    registry=REGISTRY,
)

TOKENS_TOTAL = Counter(
    "directai_embed_tokens_processed_total",
    "Total tokens processed by the embedding model.",
    registry=REGISTRY,
)


def metrics_response_body() -> bytes:
    from prometheus_client import generate_latest

    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    from prometheus_client import CONTENT_TYPE_LATEST

    return CONTENT_TYPE_LATEST
