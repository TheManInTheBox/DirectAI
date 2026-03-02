"""Tests for health endpoints."""

from pathlib import Path
from unittest.mock import PropertyMock, patch

from fastapi.testclient import TestClient


def test_healthz(test_client):
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_with_models(test_client):
    response = test_client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["models"] > 0


def test_readyz_503_no_models(monkeypatch: "pytest.MonkeyPatch", tmp_path: Path):
    """readyz returns 503 when no models are loaded."""
    # Create empty model config dir — no YAML files
    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("DIRECTAI_API_KEYS", "")

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/readyz")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not ready"
