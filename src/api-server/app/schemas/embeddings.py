"""
Pydantic models for OpenAI-compatible embeddings requests and responses.

Reference: https://platform.openai.com/docs/api-reference/embeddings
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Request ─────────────────────────────────────────────────────────

_MAX_EMBEDDING_INPUTS = 2048


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]
    encoding_format: Literal["float", "base64"] | None = "float"
    dimensions: int | None = None
    user: str | None = None

    @field_validator("input")
    @classmethod
    def validate_input_length(cls, v):
        if isinstance(v, list) and len(v) > _MAX_EMBEDDING_INPUTS:
            raise ValueError(f"Input array exceeds maximum of {_MAX_EMBEDDING_INPUTS} items.")
        return v


# ── Response ────────────────────────────────────────────────────────────


class EmbeddingData(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage
