"""
Pydantic models for OpenAI-compatible audio transcription requests and responses.

Reference: https://platform.openai.com/docs/api-reference/audio/createTranscription
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# ── Request ─────────────────────────────────────────────────────────────
# Note: The actual request is multipart/form-data. FastAPI handles the
# file upload via UploadFile; the remaining fields come from Form().
# This model is for documentation / internal use, not direct parsing.


class TranscriptionRequest(BaseModel):
    model: str
    language: str | None = None
    prompt: str | None = None
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] | None = "json"
    temperature: float | None = None


# ── Response ────────────────────────────────────────────────────────────


class TranscriptionResponse(BaseModel):
    text: str


class TranscriptionSegment(BaseModel):
    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: list[int]
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float


class VerboseTranscriptionResponse(BaseModel):
    task: str = "transcribe"
    language: str
    duration: float
    text: str
    segments: list[TranscriptionSegment] | None = None
