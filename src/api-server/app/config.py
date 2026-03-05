"""
DirectAI API Server — Settings.

Loaded from environment variables. All config is externalised;
nothing is hardcoded for a specific cluster or customer.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


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
    # ── Rate limiting ───────────────────────────────────────────────
    rate_limit_rpm: int = Field(
        default=60,
        description="Default requests per minute per API key (Open Source tier). Tier-aware limits override this.",
    )
    rate_limit_tpm: int = Field(
        default=100_000,
        description="Default tokens per minute per API key (Open Source tier). Tier-aware limits override this.",
    )
    rate_limit_max_buckets: int = Field(
        default=50_000,
        description="Hard cap on tracked keys — prevents OOM under DDoS.",
    )

    # ── Spending limits ──────────────────────────────────────
    developer_monthly_credit_cents: int = Field(
        default=500,
        description="Open Source tier monthly credit cap in cents ($5.00 = 500).",
    )
    spend_cache_ttl: float = Field(
        default=30.0,
        description="TTL in seconds for cached monthly spend lookups.",
    )

    # ── Database (model lifecycle persistence) ──────────────────
    database_path: str = Field(
        default="/app/data/directai.db",
        description="SQLite database file path. Use ':memory:' for ephemeral storage.",
    )

    # ── PostgreSQL (API key store + usage metering) ─────────────
    database_url: str = Field(
        default="",
        description="PostgreSQL connection string for API key validation and usage metering. Empty = disabled.",
    )
    key_cache_ttl: float = Field(
        default=60.0,
        description="TTL in seconds for API key validation cache.",
    )

    # ── Stripe (legacy — kept for reference, no longer used) ──────
    # Token-based metering has been removed. DirectAI uses flat management
    # fees ($3K/mo Managed, custom Enterprise). These fields are retained
    # so existing env vars don't cause startup errors, but nothing reads them.
    stripe_secret_key: str = Field(
        default="",
        description="(Unused) Stripe API secret key — token metering removed.",
    )
    stripe_meter_id_tokens: str = Field(
        default="",
        description="(Unused) Stripe Meter ID — token metering removed.",
    )
    usage_report_interval: float = Field(
        default=60.0,
        description="(Unused) Seconds between usage report flushes — token metering removed.",
    )

    # ── Tracing (OpenTelemetry) ──────────────────────────────────
    otel_enabled: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing. Requires at least one exporter.",
    )
    appinsights_connection_string: str = Field(
        default="",
        description="Azure Application Insights connection string. Empty = no Azure export.",
    )
    otlp_endpoint: str = Field(
        default="",
        description="OTLP gRPC endpoint for local dev (e.g., http://localhost:4317).",
    )
    otel_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sampling rate (0.0 = none, 1.0 = all).",
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
        return len(self.api_key_set) > 0 or bool(self.database_url)


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
