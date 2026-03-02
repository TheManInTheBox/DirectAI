"""Tests for POST /v1/audio/transcriptions."""

import io


def test_audio_model_not_found(test_client):
    response = test_client.post(
        "/v1/audio/transcriptions",
        data={"model": "nonexistent-model"},
        files={"file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_audio_wrong_modality(test_client):
    """Sending a transcription request to a chat model should return 400."""
    response = test_client.post(
        "/v1/audio/transcriptions",
        data={"model": "test-chat"},
        files={"file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
    )
    assert response.status_code == 400
    assert "chat" in response.json()["detail"].lower()


def test_audio_wrong_modality_embedding(test_client):
    """Sending a transcription request to an embedding model should return 400."""
    response = test_client.post(
        "/v1/audio/transcriptions",
        data={"model": "test-embed"},
        files={"file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
    )
    assert response.status_code == 400
    assert "embedding" in response.json()["detail"].lower()


def test_audio_resolves_whisper_alias(test_client):
    """whisper-1 alias from conftest should resolve to the transcription model."""
    # This will fail at the backend proxy (502) since there's no real backend,
    # but it should NOT return 404 — the alias must resolve.
    response = test_client.post(
        "/v1/audio/transcriptions",
        data={"model": "whisper-1"},
        files={"file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
    )
    # 502 means model was found but backend is unreachable — that's correct
    assert response.status_code == 502
