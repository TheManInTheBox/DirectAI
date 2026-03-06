"""
Audit record Pydantic models.

Defines the structured audit record schema for every inference request.
These records are written to PostgreSQL (queryable) and Blob Storage
(tamper-proof archival).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditInputSummary(BaseModel):
    """Summary of request input (not full content — that goes to Blob only)."""

    token_count: int = 0
    message_count: int = 0  # For chat: number of messages in the conversation


class AuditOutputSummary(BaseModel):
    """Summary of response output."""

    token_count: int = 0
    finish_reason: Optional[str] = None
    is_partial: bool = False  # True if client disconnected mid-stream


class GuardrailsResult(BaseModel):
    """Results from guardrails checks (populated when Milestone #4 ships)."""

    content_safety: Optional[dict[str, Any]] = None
    pii_detected: Optional[bool] = None
    injection_detected: Optional[bool] = None


class AuditRecord(BaseModel):
    """Structured audit record for a single inference request.

    Written to PostgreSQL (indexed fields only) and Blob Storage
    (full record including request/response bodies).
    """

    # ── Identity ────────────────────────────────────────────────
    request_id: str = Field(..., description="Correlation ID (X-Request-ID)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request timestamp (UTC)",
    )

    # ── Auth context ────────────────────────────────────────────
    user_id: Optional[str] = Field(None, description="User ID from API key lookup")
    api_key_id: Optional[str] = Field(None, description="API key ID (not the raw key)")
    api_key_prefix: Optional[str] = Field(None, description="First 12 chars of API key for identification")

    # ── Request metadata ────────────────────────────────────────
    method: str = Field(..., description="HTTP method (POST, GET, etc.)")
    path: str = Field(..., description="Request path (/v1/chat/completions, etc.)")
    model: Optional[str] = Field(None, description="Resolved model name")
    modality: Optional[str] = Field(None, description="chat, embedding, transcription")

    # ── Input/Output summaries ──────────────────────────────────
    input_summary: AuditInputSummary = Field(default_factory=AuditInputSummary)
    output_summary: AuditOutputSummary = Field(default_factory=AuditOutputSummary)

    # ── Guardrails (placeholder for Milestone #4) ───────────────
    guardrails: Optional[GuardrailsResult] = None

    # ── Performance ─────────────────────────────────────────────
    latency_ms: float = Field(0.0, description="End-to-end request latency in ms")
    status_code: int = Field(0, description="HTTP response status code")

    # ── Client metadata ─────────────────────────────────────────
    ip_address: Optional[str] = Field(None, description="Hashed client IP (SHA-256)")
    user_agent: Optional[str] = Field(None, description="Client User-Agent header")

    # ── Full bodies (Blob Storage only — NOT written to PostgreSQL) ──
    request_body: Optional[dict[str, Any]] = Field(
        None,
        description="Full request body (Blob only, excluded from PG writes)",
        exclude=True,  # Excluded from default serialization
    )
    response_body: Optional[str] = Field(
        None,
        description="Full response body or assembled stream (Blob only)",
        exclude=True,
    )

    def to_pg_row(self) -> dict[str, Any]:
        """Extract fields for PostgreSQL INSERT (excludes full bodies)."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
            "method": self.method,
            "path": self.path,
            "model": self.model,
            "modality": self.modality,
            "input_tokens": self.input_summary.token_count,
            "output_tokens": self.output_summary.token_count,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms),
            "guardrails_result": (
                self.guardrails.model_dump() if self.guardrails else None
            ),
        }

    def to_blob_dict(self) -> dict[str, Any]:
        """Full record for Blob Storage (includes bodies)."""
        d = self.model_dump(mode="json")
        d["request_body"] = self.request_body
        d["response_body"] = self.response_body
        return d
