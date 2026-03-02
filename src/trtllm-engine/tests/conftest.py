"""
Shared test fixtures for the TRT-LLM inference engine.

The engine runs in STUB MODE during tests — tensorrt_llm is not installed,
so the runner returns placeholder responses. This lets us validate the full
HTTP layer (routing, schemas, streaming, backpressure, metrics) without GPU.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# ── Force stub mode & sane defaults before any imports ──────────────
os.environ["TRTLLM_ENGINE_DIR"] = "/tmp/fake-engine"
os.environ["TRTLLM_TOKENIZER_DIR"] = "/tmp/fake-tokenizer"
os.environ["TRTLLM_MODEL_NAME"] = "test-model"
os.environ["TRTLLM_LOG_LEVEL"] = "warning"
os.environ["TRTLLM_MAX_INFLIGHT_REQUESTS"] = "4"  # Low limit for backpressure tests


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings between tests."""
    from engine.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_mock_tokenizer() -> MagicMock:
    """Build a mock tokenizer that satisfies runner + chat_format needs."""
    tok = MagicMock()
    tok.eos_token_id = 2
    tok.pad_token_id = 0
    tok.pad_token = "<pad>"
    tok.eos_token = "</s>"

    # encode() → list of ints (for prompt_tokens counting)
    tok.encode.return_value = [1, 2, 3, 4, 5]  # 5 prompt tokens

    # apply_chat_template() → formatted prompt string
    tok.apply_chat_template.return_value = "<|user|>\nHello\n<|assistant|>\n"

    return tok


@pytest.fixture()
def mock_tokenizer() -> MagicMock:
    return _make_mock_tokenizer()


@pytest.fixture()
def client() -> TestClient:
    """
    TestClient with stub-mode runner.

    Patches AutoTokenizer.from_pretrained so load() doesn't hit disk.
    The import is deferred (inside load()), so we patch it at the
    transformers module level.
    """
    from unittest.mock import patch

    from engine.main import app  # noqa: F811

    mock_tok = _make_mock_tokenizer()

    with patch("transformers.AutoTokenizer") as mock_auto:
        mock_auto.from_pretrained.return_value = mock_tok
        with TestClient(app) as c:
            yield c
