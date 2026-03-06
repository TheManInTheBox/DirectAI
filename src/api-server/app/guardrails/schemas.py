"""
Guardrails — Pydantic models for content safety checks.

Defines the structured error response for blocked requests and the
safety check result model used by both input and output filtering.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SafetyCategory(str, Enum):
    """Azure AI Content Safety severity categories."""

    HATE = "Hate"
    SELF_HARM = "SelfHarm"
    SEXUAL = "Sexual"
    VIOLENCE = "Violence"


class CategoryResult(BaseModel):
    """Per-category severity result from Content Safety API."""

    severity: int = Field(ge=0, le=6, description="Severity 0 (safe) to 6 (severe).")
    filtered: bool = Field(default=False, description="True if this category triggered a block.")


class SafetyCheckResult(BaseModel):
    """Aggregated result of a content safety check."""

    categories: dict[str, CategoryResult] = Field(
        default_factory=dict,
        description="Severity scores per category.",
    )
    blocked: bool = Field(default=False, description="True if any category exceeded threshold.")
    latency_ms: float = Field(default=0.0, description="Time spent calling Content Safety API.")

    @property
    def max_severity(self) -> int:
        """Return the highest severity across all categories."""
        if not self.categories:
            return 0
        return max(c.severity for c in self.categories.values())

    def to_guardrails_result(self) -> dict[str, Any]:
        """Convert to the format stored in audit records (GuardrailsResult)."""
        return {
            "content_safety": {
                name: {"severity": cat.severity, "filtered": cat.filtered}
                for name, cat in self.categories.items()
            },
            "blocked": self.blocked,
            "max_severity": self.max_severity,
        }


class ContentFilterErrorDetail(BaseModel):
    """OpenAI-compatible content filter error response body."""

    message: str = "Content blocked by safety filter"
    type: str = "content_filter_error"
    code: str = "content_filtered"
    categories: dict[str, CategoryResult] = Field(default_factory=dict)


class ContentFilterErrorResponse(BaseModel):
    """Wrapper matching OpenAI's error envelope."""

    error: ContentFilterErrorDetail
