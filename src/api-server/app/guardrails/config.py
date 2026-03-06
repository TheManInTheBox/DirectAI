"""
Guardrails — Configuration dataclass.

Mirrors the ``DIRECTAI_CONTENT_SAFETY_*`` settings from ``app.config``
into a lightweight frozen dataclass used by the middleware and client.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuardrailsConfig:
    """Content safety configuration — built from env vars at startup."""

    # Master toggle
    enabled: bool = False

    # Azure AI Content Safety endpoint and key
    # When empty, the client runs in stub/dry-run mode (always passes).
    endpoint: str = ""
    api_key: str = ""
    api_version: str = "2024-09-01"

    # Default block threshold (severity 0-6). Block if ANY category >= threshold.
    threshold: int = 4

    # Per-category threshold overrides (category name → severity).
    # Categories not listed here use the default threshold.
    category_thresholds: dict[str, int] = field(default_factory=dict)

    # Whether to check output (response) content in addition to input.
    check_output: bool = True

    # Streaming: buffer this many accumulated chars before running a safety check.
    stream_check_interval_chars: int = 2000

    # Tiers that bypass safety checks (still logs scores).
    bypass_tiers: frozenset[str] = field(default_factory=lambda: frozenset({"enterprise"}))

    # Timeout for Content Safety API calls (seconds).
    timeout: float = 2.0

    @property
    def is_live(self) -> bool:
        """True if a real Content Safety endpoint is configured."""
        return bool(self.endpoint and self.api_key)
