"""
Shared test fixtures for the embeddings inference engine.

The ONNX model and GPU are not available in CI/test, so we mock the
EmbeddingModel and let the real DynamicBatcher wrap the mock. This validates
the full HTTP + batching pipeline.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Sane defaults before any imports ────────────────────────────────
os.environ["EMBED_MODEL_PATH"] = "/tmp/fake-model.onnx"
os.environ["EMBED_TOKENIZER_PATH"] = "/tmp/fake-tokenizer"
os.environ["EMBED_MODEL_NAME"] = "test-embed-model"
os.environ["EMBED_LOG_LEVEL"] = "warning"
os.environ["EMBED_EXECUTION_PROVIDER"] = "CPUExecutionProvider"
os.environ["EMBED_MAX_BATCH_SIZE"] = "32"


EMBED_DIM = 384  # Simulated embedding dimension


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear lru_cache on get_settings between tests."""
    from engine.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_mock_model() -> MagicMock:
    """
    Build a mock EmbeddingModel.

    embed(texts) returns a numpy array of shape [len(texts), EMBED_DIM]
    filled with deterministic values so tests can assert on shapes.
    """
    model = MagicMock()
    model.is_loaded = True
    model.embedding_dim = EMBED_DIM

    def fake_embed(texts: list[str]) -> np.ndarray:
        # Each text gets a unique-ish embedding based on its index
        n = len(texts)
        rng = np.random.RandomState(42)
        embs = rng.randn(n, EMBED_DIM).astype(np.float32)
        # L2 normalize like a real model
        norms = np.linalg.norm(embs, axis=1, keepdims=True).clip(min=1e-12)
        return embs / norms

    model.embed.side_effect = fake_embed
    model.load.return_value = None
    model.count_tokens.side_effect = lambda text: len(text.split())
    return model


@pytest.fixture()
def mock_model() -> MagicMock:
    return _make_mock_model()


@pytest.fixture()
def client() -> TestClient:
    """
    TestClient with a mocked EmbeddingModel.

    Patches EmbeddingModel so we skip ONNX loading. The real DynamicBatcher
    wraps the mock, so the batching path is exercised.
    """
    mock_model = _make_mock_model()

    with patch("engine.main.EmbeddingModel", return_value=mock_model):
        from engine.main import app

        with TestClient(app) as c:
            yield c
