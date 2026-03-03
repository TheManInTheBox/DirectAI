"""
Tests for DirectAI-native API — Deployment management.

POST   /api/v1/deployments           Create
GET    /api/v1/deployments           List
GET    /api/v1/deployments/{id}      Get
PATCH  /api/v1/deployments/{id}      Update
DELETE /api/v1/deployments/{id}      Terminate

Also tests routing integration: when a deployment transitions to
'running' with an endpoint_url, the model should appear in the
inference routing table (GET /v1/models).
"""

from __future__ import annotations

# ── Helpers ──────────────────────────────────────────────────────────

_MODEL_BODY = {
    "name": "deploy-test-model",
    "version": "1.0",
    "architecture": "llama",
    "parameter_count": 7_000_000_000,
    "modality": "chat",
    "weight_uri": "az://models/llama-7b/",
    "required_gpu_sku": "Standard_ND96asr_v4",
    "tp_degree": 1,
}


def _create_model(client, **overrides):
    body = {**_MODEL_BODY, **overrides}
    resp = client.post("/api/v1/models", json=body)
    assert resp.status_code == 201
    return resp.json()


# ── Tests ────────────────────────────────────────────────────────────


class TestCreateDeployment:
    """POST /api/v1/deployments"""

    def test_success(self, test_client):
        model = _create_model(test_client)
        resp = test_client.post("/api/v1/deployments", json={
            "model_id": model["id"],
            "scaling_tier": "always-warm",
            "min_replicas": 1,
            "max_replicas": 8,
            "target_concurrency": 16,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["model_id"] == model["id"]
        assert data["status"] == "pending"
        assert data["scaling_tier"] == "always-warm"
        assert data["min_replicas"] == 1
        assert data["max_replicas"] == 8
        assert data["endpoint_url"] is None

    def test_defaults_applied(self, test_client):
        model = _create_model(test_client)
        resp = test_client.post("/api/v1/deployments", json={
            "model_id": model["id"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["scaling_tier"] == "always-warm"
        assert data["min_replicas"] == 1
        assert data["max_replicas"] == 4
        assert data["target_concurrency"] == 8

    def test_nonexistent_model_returns_422(self, test_client):
        resp = test_client.post("/api/v1/deployments", json={
            "model_id": "nonexistent-id",
        })
        assert resp.status_code == 422
        assert "not found" in resp.json()["detail"].lower()

    def test_failed_model_not_deployable(self, test_client):
        model = _create_model(test_client)
        # Transition to failed
        test_client.patch(
            f"/api/v1/models/{model['id']}", json={"status": "failed"},
        )
        resp = test_client.post("/api/v1/deployments", json={
            "model_id": model["id"],
        })
        assert resp.status_code == 422
        assert "status" in resp.json()["detail"].lower()


class TestListDeployments:
    """GET /api/v1/deployments"""

    def test_empty_list(self, test_client):
        resp = test_client.get("/api/v1/deployments")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_returns_deployments(self, test_client):
        model = _create_model(test_client)
        test_client.post("/api/v1/deployments", json={"model_id": model["id"]})
        test_client.post("/api/v1/deployments", json={"model_id": model["id"]})
        resp = test_client.get("/api/v1/deployments")
        assert resp.json()["count"] == 2

    def test_filter_by_status(self, test_client):
        model = _create_model(test_client)
        test_client.post("/api/v1/deployments", json={"model_id": model["id"]})
        resp = test_client.get("/api/v1/deployments?status=pending")
        assert resp.json()["count"] == 1
        resp2 = test_client.get("/api/v1/deployments?status=running")
        assert resp2.json()["count"] == 0

    def test_filter_by_model_id(self, test_client):
        m1 = _create_model(test_client, name="m1")
        m2 = _create_model(test_client, name="m2")
        test_client.post("/api/v1/deployments", json={"model_id": m1["id"]})
        test_client.post("/api/v1/deployments", json={"model_id": m2["id"]})
        resp = test_client.get(f"/api/v1/deployments?model_id={m1['id']}")
        assert resp.json()["count"] == 1


class TestGetDeployment:
    """GET /api/v1/deployments/{id}"""

    def test_found(self, test_client):
        model = _create_model(test_client)
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]
        resp = test_client.get(f"/api/v1/deployments/{dep_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == dep_id

    def test_not_found(self, test_client):
        resp = test_client.get("/api/v1/deployments/nonexistent")
        assert resp.status_code == 404


class TestUpdateDeployment:
    """PATCH /api/v1/deployments/{id}"""

    def test_update_scaling(self, test_client):
        model = _create_model(test_client)
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]
        resp = test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "min_replicas": 2,
            "max_replicas": 16,
            "target_concurrency": 32,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_replicas"] == 2
        assert data["max_replicas"] == 16
        assert data["target_concurrency"] == 32

    def test_update_status_to_provisioning(self, test_client):
        model = _create_model(test_client)
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]
        resp = test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "status": "provisioning",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "provisioning"

    def test_not_found(self, test_client):
        resp = test_client.patch(
            "/api/v1/deployments/nonexistent", json={"status": "running"},
        )
        assert resp.status_code == 404


class TestDeleteDeployment:
    """DELETE /api/v1/deployments/{id}"""

    def test_terminate(self, test_client):
        model = _create_model(test_client)
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]
        resp = test_client.delete(f"/api/v1/deployments/{dep_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"

    def test_not_found(self, test_client):
        resp = test_client.delete("/api/v1/deployments/nonexistent")
        assert resp.status_code == 404


class TestRoutingIntegration:
    """When deployment goes running with endpoint_url, model becomes routable."""

    def test_running_deployment_registers_in_router(self, test_client):
        model = _create_model(test_client, name="routable-model")
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]

        # Model should NOT appear in /v1/models yet (only YAML models do)
        models_before = test_client.get("/v1/models").json()["data"]
        routable_before = [m for m in models_before if m["id"] == "routable-model"]
        assert len(routable_before) == 0

        # Transition to running with endpoint URL
        test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "status": "running",
            "endpoint_url": "http://routable-model.directai.svc.cluster.local:8001",
        })

        # NOW the model should appear in /v1/models
        models_after = test_client.get("/v1/models").json()["data"]
        routable_after = [m for m in models_after if m["id"] == "routable-model"]
        assert len(routable_after) == 1

        # And the model status in the native API should be "deployed"
        native_model = test_client.get(f"/api/v1/models/{model['id']}").json()
        assert native_model["status"] == "deployed"

    def test_terminated_deployment_unregisters_from_router(self, test_client):
        model = _create_model(test_client, name="teardown-model")
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]

        # Make it running
        test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "status": "running",
            "endpoint_url": "http://teardown-model.directai.svc.cluster.local:8001",
        })
        models_running = test_client.get("/v1/models").json()["data"]
        assert any(m["id"] == "teardown-model" for m in models_running)

        # Terminate
        test_client.delete(f"/api/v1/deployments/{dep_id}")

        # Should be removed from routing
        models_after = test_client.get("/v1/models").json()["data"]
        assert not any(m["id"] == "teardown-model" for m in models_after)

    def test_failed_deployment_unregisters_from_router(self, test_client):
        model = _create_model(test_client, name="fail-model")
        dep_id = test_client.post(
            "/api/v1/deployments", json={"model_id": model["id"]},
        ).json()["id"]

        # Make it running
        test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "status": "running",
            "endpoint_url": "http://fail-model.directai.svc.cluster.local:8001",
        })

        # Mark as failed
        test_client.patch(f"/api/v1/deployments/{dep_id}", json={
            "status": "failed",
        })

        models_after = test_client.get("/v1/models").json()["data"]
        assert not any(m["id"] == "fail-model" for m in models_after)
