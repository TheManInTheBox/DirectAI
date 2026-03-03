"""
Tests for DirectAI-native API — Model lifecycle management.

POST   /api/v1/models           Register
GET    /api/v1/models           List
GET    /api/v1/models/{id}      Get
PATCH  /api/v1/models/{id}      Update status / engine_artifacts
DELETE /api/v1/models/{id}      Deregister
"""

from __future__ import annotations

# ── Helpers ──────────────────────────────────────────────────────────

_REGISTER_BODY = {
    "name": "test-llama",
    "version": "1.0",
    "architecture": "llama",
    "parameter_count": 70_000_000_000,
    "modality": "chat",
    "weight_uri": "az://models/llama-70b/",
    "required_gpu_sku": "Standard_ND96asr_v4",
    "tp_degree": 2,
}


def _register(client, **overrides):
    body = {**_REGISTER_BODY, **overrides}
    return client.post("/api/v1/models", json=body)


# ── Tests ────────────────────────────────────────────────────────────


class TestRegisterModel:
    """POST /api/v1/models"""

    def test_success(self, test_client):
        resp = _register(test_client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-llama"
        assert data["version"] == "1.0"
        assert data["architecture"] == "llama"
        assert data["parameter_count"] == 70_000_000_000
        assert data["modality"] == "chat"
        assert data["status"] == "registered"
        assert data["engine_artifacts"] == {}
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_duplicate_version_returns_409(self, test_client):
        resp1 = _register(test_client)
        assert resp1.status_code == 201
        resp2 = _register(test_client)
        assert resp2.status_code == 409
        assert "immutable" in resp2.json()["detail"].lower()

    def test_different_versions_ok(self, test_client):
        resp1 = _register(test_client, version="1.0")
        resp2 = _register(test_client, version="2.0")
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_defaults_applied(self, test_client):
        resp = _register(test_client)
        data = resp.json()
        assert data["quantization"] == "fp16"
        assert data["format"] == "safetensors"

    def test_missing_required_fields_returns_422(self, test_client):
        resp = test_client.post("/api/v1/models", json={"name": "incomplete"})
        assert resp.status_code == 422


class TestListModels:
    """GET /api/v1/models"""

    def test_empty_list(self, test_client):
        resp = test_client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["data"] == []

    def test_returns_registered_models(self, test_client):
        _register(test_client, name="model-a", version="1.0")
        _register(test_client, name="model-b", version="1.0")
        resp = test_client.get("/api/v1/models")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_filter_by_status(self, test_client):
        _register(test_client, name="m1", version="1.0")
        resp = test_client.get("/api/v1/models?status=registered")
        assert resp.json()["count"] == 1
        resp2 = test_client.get("/api/v1/models?status=ready")
        assert resp2.json()["count"] == 0

    def test_filter_by_architecture(self, test_client):
        _register(test_client, name="m1", version="1.0", architecture="llama")
        _register(test_client, name="m2", version="1.0", architecture="qwen")
        resp = test_client.get("/api/v1/models?architecture=llama")
        assert resp.json()["count"] == 1
        assert resp.json()["data"][0]["architecture"] == "llama"

    def test_filter_by_modality(self, test_client):
        _register(test_client, name="emb", version="1.0", modality="embedding")
        _register(test_client, name="chat", version="1.0", modality="chat")
        resp = test_client.get("/api/v1/models?modality=embedding")
        assert resp.json()["count"] == 1


class TestGetModel:
    """GET /api/v1/models/{id}"""

    def test_found(self, test_client):
        model_id = _register(test_client).json()["id"]
        resp = test_client.get(f"/api/v1/models/{model_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == model_id

    def test_not_found(self, test_client):
        resp = test_client.get("/api/v1/models/nonexistent-id")
        assert resp.status_code == 404


class TestUpdateModel:
    """PATCH /api/v1/models/{id}"""

    def test_update_status(self, test_client):
        model_id = _register(test_client).json()["id"]
        resp = test_client.patch(
            f"/api/v1/models/{model_id}",
            json={"status": "building"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "building"

    def test_update_engine_artifacts(self, test_client):
        model_id = _register(test_client).json()["id"]
        artifacts = {"Standard_ND96asr_v4": "az://engines/llama-70b-a100/"}
        resp = test_client.patch(
            f"/api/v1/models/{model_id}",
            json={"status": "ready", "engine_artifacts": artifacts},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert resp.json()["engine_artifacts"] == artifacts

    def test_empty_update_returns_422(self, test_client):
        model_id = _register(test_client).json()["id"]
        resp = test_client.patch(f"/api/v1/models/{model_id}", json={})
        assert resp.status_code == 422

    def test_not_found(self, test_client):
        resp = test_client.patch(
            "/api/v1/models/nonexistent", json={"status": "building"},
        )
        assert resp.status_code == 404


class TestDeleteModel:
    """DELETE /api/v1/models/{id}"""

    def test_delete_success(self, test_client):
        model_id = _register(test_client).json()["id"]
        resp = test_client.delete(f"/api/v1/models/{model_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == model_id
        # Verify it's gone
        assert test_client.get(f"/api/v1/models/{model_id}").status_code == 404

    def test_delete_not_found(self, test_client):
        resp = test_client.delete("/api/v1/models/nonexistent")
        assert resp.status_code == 404

    def test_delete_blocked_by_active_deployment(self, test_client):
        model_id = _register(test_client).json()["id"]
        # Create a deployment (status=pending → active)
        test_client.post("/api/v1/deployments", json={"model_id": model_id})
        resp = test_client.delete(f"/api/v1/models/{model_id}")
        assert resp.status_code == 409
        assert "active deployment" in resp.json()["detail"].lower()

    def test_delete_ok_after_deployment_terminated(self, test_client):
        model_id = _register(test_client).json()["id"]
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model_id},
        ).json()["id"]
        # Terminate the deployment
        test_client.delete(f"/api/v1/deployments/{dep_id}")
        # Now delete should succeed
        resp = test_client.delete(f"/api/v1/models/{model_id}")
        assert resp.status_code == 200
