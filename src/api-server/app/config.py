"""
DirectAI API Server — Settings.

Loaded from environment variables. All config is externalised;
nothing is hardcoded for a specific cluster or customer.
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = {"env_prefix": "DIRECTAI_", "env_file": ".env", "extra": "ignore"}

    # ── Server ──────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    debug: bool = False

    # ── Model registry ──────────────────────────────────────────────────
    # Path to directory containing ModelDeployment YAML files.
    model_config_dir: Path = Field(
        default=Path("/app/models"),
        description="Directory containing ModelDeployment YAML files.",
    )

    # ── Auth ────────────────────────────────────────────────────────────
    # Comma-separated list of valid API keys. In production, replaced by
    # Key Vault–backed lookup (see auth module).
    api_keys: str = Field(
        default="",
        description="Comma-separated API keys. Empty = auth disabled (dev only).",
    )

    # ── Backend ─────────────────────────────────────────────────────────
    # Timeout for proxied requests to inference backends (seconds).
    backend_timeout: float = 300.0
    # Timeout for backend connect phase only.
    backend_connect_timeout: float = 5.0

    @property
    def api_key_set(self) -> set[str]:
        """Parsed set of valid API keys."""
        if not self.api_keys:
            return set()
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def auth_enabled(self) -> bool:
        return len(self.api_key_set) > 0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton.

    The ``@lru_cache`` ensures environment variables are read exactly once
    at first import — subsequent calls return the same ``Settings`` instance.
    This is intentional for performance (avoid re-parsing on every request).

    **Testing:** Call ``get_settings.cache_clear()`` after monkeypatching
    environment variables so the next call picks up the new values.

    **Production override:** If you need live-reloadable config (e.g. Key
    Vault rotation), replace this with a dependency that reads from an
    external store and caches with a TTL.
    """
    return Settings()
