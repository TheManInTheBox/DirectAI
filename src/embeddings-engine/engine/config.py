"""
Configuration for the embeddings inference engine.

All settings use the EMBED_ prefix and can be set via environment variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Embeddings engine configuration."""

    model_config = {"env_prefix": "EMBED_"}

    # ── Server ──────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8001

    # ── Model ───────────────────────────────────────────────────────
    model_path: str = "/models/model.onnx"
    tokenizer_path: str = "/models/tokenizer.json"
    model_name: str = "bge-large-en-v1.5"
    max_seq_length: int = 512

    # ── Batching ────────────────────────────────────────────────────
    max_batch_size: int = 256
    batch_timeout_ms: float = 5.0  # Max wait to fill a batch (ms)

    # ── Runtime ─────────────────────────────────────────────────────
    num_threads: int = 4  # ONNX Runtime intra-op threads
    execution_provider: str = "CUDAExecutionProvider"  # or CPUExecutionProvider

    # ── Normalization ───────────────────────────────────────────────
    normalize_embeddings: bool = True

    # ── Observability ───────────────────────────────────────────────
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
