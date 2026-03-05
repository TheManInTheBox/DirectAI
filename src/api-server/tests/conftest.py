"""
Shared test fixtures for the DirectAI API server.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure auth is disabled for tests unless explicitly set
os.environ.setdefault("DIRECTAI_API_KEYS", "")
# High rate limits for tests so non-rate-limit tests aren't throttled.
# The rate limiter middleware captures these at module import time.
os.environ.setdefault("DIRECTAI_RATE_LIMIT_RPM", "100000")
os.environ.setdefault("DIRECTAI_RATE_LIMIT_TPM", "100000000")


# ── Sample model config YAML ────────────────────────────────────────

CHAT_MODEL_YAML = """
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: test-chat-model
spec:
  displayName: "Test Chat Model"
  ownedBy: test
  modality: chat
  engine:
    type: tensorrt-llm
    image: "test/trtllm:latest"
    weightsUri: "az://test/weights/"
  hardware:
    gpuSku: Standard_ND96asr_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: always-warm
    minReplicas: 1
    maxReplicas: 2
    targetConcurrency: 4
  api:
    aliases:
      - test-chat
      - org/test-chat
"""

EMBEDDING_MODEL_YAML = """
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: test-embedding-model
spec:
  displayName: "Test Embedding Model"
  ownedBy: test
  modality: embedding
  engine:
    type: onnxruntime
    image: "test/onnx:latest"
    weightsUri: "az://test/weights/"
    maxBatchSize: 128
  hardware:
    gpuSku: Standard_NC24ads_A100_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: always-warm
    minReplicas: 1
    maxReplicas: 4
    targetConcurrency: 32
  api:
    aliases:
      - test-embed
"""

TRANSCRIPTION_MODEL_YAML = """
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: test-whisper
spec:
  displayName: "Test Whisper"
  ownedBy: test
  modality: transcription
  engine:
    type: tensorrt-llm
    image: "test/whisper:latest"
    weightsUri: "az://test/weights/"
  hardware:
    gpuSku: Standard_ND96asr_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: scale-to-zero
    minReplicas: 0
    maxReplicas: 2
    targetConcurrency: 4
  api:
    aliases:
      - test-whisper
      - whisper-1
"""


@pytest.fixture()
def model_config_dir(tmp_path: Path) -> Path:
    """Create a temp directory with all three test model configs."""
    (tmp_path / "chat.yaml").write_text(CHAT_MODEL_YAML)
    (tmp_path / "embedding.yaml").write_text(EMBEDDING_MODEL_YAML)
    (tmp_path / "transcription.yaml").write_text(TRANSCRIPTION_MODEL_YAML)
    return tmp_path


@pytest.fixture()
def test_client(model_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient with test model configs loaded.

    Must enter the context manager so that the async lifespan runs —
    this is what populates app.state.model_registry / backend_client.
    """
    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
    monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
    monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
    # Override free-tier limits so integration tests aren't throttled.
    # Production free tier is 20 RPM / 40K TPM — too tight for rapid-fire tests.
    from app.middleware.rate_limit import TIER_LIMITS, TierLimits
    monkeypatch.setitem(TIER_LIMITS, "free", TierLimits(rpm=600, tpm=10_000_000))

    # Clear cached settings so env var takes effect
    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        # Reset rate limiter state after lifespan builds the middleware stack
        # to prevent 429 bleed between test classes.
        from app.middleware.rate_limit import RateLimitMiddleware
        mw = app.middleware_stack
        while mw is not None:
            if isinstance(mw, RateLimitMiddleware):
                mw.reset()
                # Apply test overrides — module-level middleware was created
                # before the monkeypatch env vars took effect.
                mw._default_rpm = 600
                mw._default_tpm = 10_000_000
                break
            mw = getattr(mw, 'app', None)
        yield client
