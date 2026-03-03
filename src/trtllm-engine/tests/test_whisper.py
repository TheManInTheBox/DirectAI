"""
Tests for the Whisper transcription endpoint (/v1/audio/transcriptions).

Uses TRTLLM_MODALITY=transcription so the engine starts in Whisper mode.
The Whisper runner operates in stub mode (no tensorrt_llm installed),
returning placeholder transcription text.
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def whisper_client():
    """TestClient with Whisper stub mode (TRTLLM_MODALITY=transcription)."""
    # Set modality BEFORE importing the app so Settings picks it up
    os.environ["TRTLLM_MODALITY"] = "transcription"

    # Clear cached settings so the modality change takes effect
    from engine.config import get_settings
    get_settings.cache_clear()

    # Must reimport app AFTER setting env, but the app is module-level.
    # Instead, rely on lifespan to branch on modality.
    from engine.main import app

    with TestClient(app) as c:
        yield c

    # Clean up
    os.environ.pop("TRTLLM_MODALITY", None)
    get_settings.cache_clear()


class TestTranscriptionEndpoint:
    """POST /v1/audio/transcriptions tests."""

    def test_basic_transcription(self, whisper_client: TestClient):
        """Stub mode returns placeholder transcription text."""
        audio_bytes = b"\x00" * 1024  # Fake audio data
        resp = whisper_client.post(
            "/v1/audio/transcriptions",
            files={"file": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")},
            data={"model": "whisper-large-v3"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        assert "[stub]" in body["text"]

    def test_transcription_with_optional_params(self, whisper_client: TestClient):
        """Optional params (language, prompt, temperature) are accepted."""
        audio_bytes = b"\x00" * 512
        resp = whisper_client.post(
            "/v1/audio/transcriptions",
            files={"file": ("audio.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
            data={
                "model": "whisper-large-v3",
                "language": "en",
                "prompt": "Technical discussion about AI.",
                "temperature": "0.2",
                "response_format": "json",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body

    def test_missing_file_returns_422(self, whisper_client: TestClient):
        """Missing file field should fail validation."""
        resp = whisper_client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-large-v3"},
        )
        assert resp.status_code == 422

    def test_missing_model_returns_422(self, whisper_client: TestClient):
        """Missing model field should fail validation."""
        audio_bytes = b"\x00" * 512
        resp = whisper_client.post(
            "/v1/audio/transcriptions",
            files={"file": ("test.wav", io.BytesIO(audio_bytes), "audio/wav")},
        )
        assert resp.status_code == 422

    def test_oversized_file_returns_413(self, whisper_client: TestClient):
        """Files larger than 25MB should be rejected."""
        # 25MB + 1 byte
        audio_bytes = b"\x00" * (25 * 1024 * 1024 + 1)
        resp = whisper_client.post(
            "/v1/audio/transcriptions",
            files={"file": ("huge.wav", io.BytesIO(audio_bytes), "audio/wav")},
            data={"model": "whisper-large-v3"},
        )
        assert resp.status_code == 413


class TestWhisperHealthProbes:
    """Health probes in transcription mode."""

    def test_healthz(self, whisper_client: TestClient):
        resp = whisper_client.get("/healthz")
        assert resp.status_code == 200

    def test_readyz(self, whisper_client: TestClient):
        """Whisper engine should be ready after lifespan init."""
        resp = whisper_client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_models_endpoint(self, whisper_client: TestClient):
        """GET /v1/models should list the whisper model."""
        resp = whisper_client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1

    def test_chat_endpoint_not_available_in_whisper_mode(
        self, whisper_client: TestClient
    ):
        """Chat completions should still be registered but fail gracefully.

        The chat endpoint calls _get_runner() which raises 503 since
        _runner is None in transcription mode.
        """
        resp = whisper_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # 503 because _runner is None (we're in Whisper mode)
        assert resp.status_code == 503
