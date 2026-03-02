"""
Configuration for the TRT-LLM inference engine.

All settings use the TRTLLM_ prefix and can be set via environment variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """TRT-LLM engine configuration."""

    model_config = {"env_prefix": "TRTLLM_"}

    # ── Server ──────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8001

    # ── Model ───────────────────────────────────────────────────────
    engine_dir: str = "/models/engine"
    tokenizer_dir: str = "/models/tokenizer"
    model_name: str = "llama-3.1-70b-instruct"

    # ── Modality ────────────────────────────────────────────────────
    # "chat" → /v1/chat/completions only
    # "transcription" → /v1/audio/transcriptions only
    modality: str = "chat"

    # ── Generation defaults ─────────────────────────────────────────
    max_batch_size: int = 64
    max_input_len: int = 4096
    max_output_len: int = 4096
    max_beam_width: int = 1

    # ── Tensor Parallelism ──────────────────────────────────────────
    tp_size: int = 1
    pp_size: int = 1  # Pipeline parallelism — Phase 2

    # ── KV Cache ────────────────────────────────────────────────────
    kv_cache_free_gpu_mem_fraction: float = 0.85
    enable_chunked_context: bool = True

    # ── Streaming ───────────────────────────────────────────────────
    streaming_token_buffer_size: int = 1  # Flush every N tokens

    # ── Backpressure ────────────────────────────────────────────────
    max_inflight_requests: int = 128  # 429 when exceeded

    # ── Observability ───────────────────────────────────────────────
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
