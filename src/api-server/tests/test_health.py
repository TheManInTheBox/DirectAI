"""Tests for health endpoints."""


def test_healthz(test_client):
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_with_models(test_client):
    response = test_client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["models"] > 0
