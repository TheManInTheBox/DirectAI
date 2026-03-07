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
        default=20,
        description="Default requests per minute per API key (Free tier). Tier-aware limits override this.",
    )
    rate_limit_tpm: int = Field(
        default=40_000,
        description="Default tokens per minute per API key (Free tier). Tier-aware limits override this.",
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

    # ── Stripe (hybrid billing — base fee + per-token metering) ──────
    stripe_secret_key: str = Field(
        default="",
        description="Stripe API secret key. Empty = dry-run mode (events logged, not sent).",
    )
    usage_report_interval: float = Field(
        default=60.0,
        description="Seconds between Stripe Meter flush cycles.",
    )
    # Per-modality Stripe Meter event names.  These must match the meter
    # event_name values configured in the Stripe dashboard.
    stripe_meter_chat_input: str = Field(
        default="chat_input_tokens",
        description="Stripe Meter event name for chat input tokens.",
    )
    stripe_meter_chat_output: str = Field(
        default="chat_output_tokens",
        description="Stripe Meter event name for chat output tokens.",
    )
    stripe_meter_embedding: str = Field(
        default="embedding_tokens",
        description="Stripe Meter event name for embedding tokens.",
    )
    stripe_meter_transcription: str = Field(
        default="transcription_seconds",
        description="Stripe Meter event name for transcription (centiseconds).",
    )

    # ── Audit logging ────────────────────────────────────────────
    audit_enabled: bool = Field(
        default=False,
        description="Enable audit logging of all inference requests.",
    )

    # ── Content safety (guardrails) ─────────────────────────────
    content_safety_enabled: bool = Field(
        default=False,
        description="Enable Azure AI Content Safety filtering on inference requests.",
    )
    content_safety_endpoint: str = Field(
        default="",
        description="Azure AI Content Safety endpoint URL. Empty = stub mode.",
    )
    content_safety_key: str = Field(
        default="",
        description="Azure AI Content Safety API key (Ocp-Apim-Subscription-Key).",
    )
    content_safety_threshold: int = Field(
        default=4,
        ge=0,
        le=6,
        description="Block if any category severity >= this value (0-6).",
    )
    content_safety_check_output: bool = Field(
        default=True,
        description="Also check LLM output (response) for safety violations.",
    )
    content_safety_stream_check_chars: int = Field(
        default=2000,
        description="Streaming: chars to accumulate between safety checks.",
    )
    content_safety_timeout: float = Field(
        default=2.0,
        description="Timeout in seconds for Content Safety API calls.",
    )
    audit_pg_enabled: bool = Field(
        default=True,
        description="Write audit records to PostgreSQL (queryable, 90-day retention).",
    )
    audit_pg_retention_days: int = Field(
        default=90,
        description="Auto-prune PG audit records older than this (days).",
    )
    audit_blob_enabled: bool = Field(
        default=False,
        description="Write audit records to Azure Immutable Blob Storage (long-term archival).",
    )
    audit_storage_account: str = Field(
        default="",
        description="Azure Storage Account name for audit blob writes.",
    )
    audit_storage_connection_string: str = Field(
        default="",
        description="Azure Storage connection string for audit blob writes. Takes precedence over account name.",
    )
    audit_storage_container: str = Field(
        default="audit-logs",
        description="Blob container name for audit records.",
    )
    audit_retention_days: int = Field(
        default=365,
        description="Blob retention period in days (Azure immutability policy).",
    )
    audit_redact_pii: bool = Field(
        default=False,
        description="Redact PII (IP addresses, request/response bodies) from blob audit records before upload.",
    )
    audit_queue_size: int = Field(
        default=50_000,
        description="Max audit records in async write queue.",
    )
    audit_flush_interval: float = Field(
        default=5.0,
        description="Seconds between audit writer flush cycles.",
    )
    audit_batch_size: int = Field(
        default=100,
        description="Max audit records per flush batch.",
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
