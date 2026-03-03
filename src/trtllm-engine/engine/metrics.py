"""
Prometheus metrics for the TRT-LLM inference engine.

Metrics:
  LLM:
    - directai_llm_inflight_requests: Gauge of requests in generation
    - directai_llm_requests_total: Counter by status
    - directai_llm_request_duration_seconds: E2E latency histogram
    - directai_llm_time_to_first_token_seconds: TTFT histogram
    - directai_llm_tokens_generated_total: Counter of output tokens
    - directai_llm_prompt_tokens_total: Counter of input tokens
  Whisper:
    - directai_whisper_requests_total: Counter by status
    - directai_whisper_request_duration_seconds: E2E latency histogram
    - directai_whisper_audio_duration_seconds: Histogram of input audio length
    - directai_whisper_preprocessing_seconds: Audio decode + mel spectrogram time
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()

INFLIGHT_REQUESTS = Gauge(
    "directai_llm_inflight_requests",
    "Number of LLM generation requests currently in-flight.",
    registry=REGISTRY,
)

REQUESTS_TOTAL = Counter(
    "directai_llm_requests_total",
    "Total LLM generation requests.",
    ["status", "stream"],  # ok/error, true/false
    registry=REGISTRY,
)

REQUEST_DURATION = Histogram(
    "directai_llm_request_duration_seconds",
    "End-to-end LLM request latency in seconds.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)

TTFT = Histogram(
    "directai_llm_time_to_first_token_seconds",
    "Time from request received to first token generated.",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

TOKENS_GENERATED = Counter(
    "directai_llm_tokens_generated_total",
    "Total output tokens generated.",
    registry=REGISTRY,
)

PROMPT_TOKENS = Counter(
    "directai_llm_prompt_tokens_total",
    "Total input prompt tokens processed.",
    registry=REGISTRY,
)

REJECTED_REQUESTS = Counter(
    "directai_llm_rejected_requests_total",
    "Requests rejected due to backpressure.",
    ["reason"],  # "overloaded"
    registry=REGISTRY,
)

# ── Whisper metrics ─────────────────────────────────────────────────

WHISPER_REQUESTS = Counter(
    "directai_whisper_requests_total",
    "Total Whisper transcription requests.",
    ["status"],  # ok/error
    registry=REGISTRY,
)

WHISPER_REQUEST_DURATION = Histogram(
    "directai_whisper_request_duration_seconds",
    "End-to-end Whisper transcription latency in seconds.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

WHISPER_AUDIO_DURATION = Histogram(
    "directai_whisper_audio_duration_seconds",
    "Duration of input audio in seconds (estimated from file size).",
    buckets=(1.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
    registry=REGISTRY,
)

WHISPER_PREPROCESSING = Histogram(
    "directai_whisper_preprocessing_seconds",
    "Time spent on audio decoding and mel spectrogram computation.",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)


def metrics_response_body() -> bytes:
    from prometheus_client import generate_latest

    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    from prometheus_client import CONTENT_TYPE_LATEST

    return CONTENT_TYPE_LATEST
