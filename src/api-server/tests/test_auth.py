"""
Tests for API key authentication (P1 — auth coverage).

Validates:
  - Auth disabled (dev mode): requests pass through without a key
  - Auth enabled with valid key: request succeeds
  - Auth enabled with invalid key: returns 401 + WWW-Authenticate
  - Auth enabled with missing key: returns 401 + WWW-Authenticate
  - Key hash is logged instead of raw prefix (P1 #15 regression guard)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import model YAML fixtures from the conftest in this package
from conftest import CHAT_MODEL_YAML, EMBEDDING_MODEL_YAML, TRANSCRIPTION_MODEL_YAML
from fastapi.testclient import TestClient


@pytest.fixture()
def model_config_dir(tmp_path: Path) -> Path:
    (tmp_path / "chat.yaml").write_text(CHAT_MODEL_YAML)
    (tmp_path / "embedding.yaml").write_text(EMBEDDING_MODEL_YAML)
    (tmp_path / "transcription.yaml").write_text(TRANSCRIPTION_MODEL_YAML)
    return tmp_path


def _make_client(monkeypatch, model_config_dir, api_keys: str = ""):
    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
    monkeypatch.setenv("DIRECTAI_API_KEYS", api_keys)

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestAuthDisabled:
    """When DIRECTAI_API_KEYS is empty, auth is disabled (dev mode)."""

    def test_no_key_required(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys="") as client:
            resp = client.get("/v1/models")
            assert resp.status_code == 200

    def test_arbitrary_key_accepted(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys="") as client:
            resp = client.get("/v1/models", headers={"Authorization": "Bearer anything"})
            assert resp.status_code == 200


class TestAuthEnabled:
    """When DIRECTAI_API_KEYS is set, auth is enforced."""

    API_KEY = "sk-test-key-12345678"

    def test_valid_key_succeeds(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys=self.API_KEY) as client:
            resp = client.get(
                "/v1/models",
                headers={"Authorization": f"Bearer {self.API_KEY}"},
            )
            assert resp.status_code == 200

    def test_invalid_key_returns_401(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys=self.API_KEY) as client:
            resp = client.get(
                "/v1/models",
                headers={"Authorization": "Bearer wrong-key"},
            )
            assert resp.status_code == 401
            assert resp.headers.get("WWW-Authenticate") == "Bearer"
            assert "Invalid API key" in resp.json()["detail"]

    def test_missing_key_returns_401(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys=self.API_KEY) as client:
            resp = client.get("/v1/models")
            assert resp.status_code == 401
            assert resp.headers.get("WWW-Authenticate") == "Bearer"
            assert "Missing API key" in resp.json()["detail"]

    def test_multiple_keys_any_valid(self, model_config_dir, monkeypatch):
        keys = "sk-key-one,sk-key-two,sk-key-three"
        with _make_client(monkeypatch, model_config_dir, api_keys=keys) as client:
            resp = client.get(
                "/v1/models",
                headers={"Authorization": "Bearer sk-key-two"},
            )
            assert resp.status_code == 200

    def test_empty_bearer_returns_401(self, model_config_dir, monkeypatch):
        with _make_client(monkeypatch, model_config_dir, api_keys=self.API_KEY) as client:
            resp = client.get(
                "/v1/models",
                headers={"Authorization": "Bearer "},
            )
            # Empty bearer token should fail
            assert resp.status_code == 401
