"""
Tests for DirectAI-native API — System endpoints + status_url.

GET  /api/v1/health       Service health snapshot
GET  /api/v1/gpu-pools    GPU pool capacity summary
                          + status_url on deployment responses
"""

from __future__ import annotations

# ── Helpers ──────────────────────────────────────────────────────────

_MODEL_BODY = {
    "name": "sys-test-model",
    "version": "1.0",
    "architecture": "llama",
    "parameter_count": 7_000_000_000,
    "modality": "chat",
    "weight_uri": "az://models/llama-7b/",
    "required_gpu_sku": "Standard_ND96asr_v4",
    "tp_degree": 2,
}


def _create_model(client, **overrides):
    body = {**_MODEL_BODY, **overrides}
    resp = client.post("/api/v1/models", json=body)
    assert resp.status_code == 201
    return resp.json()


def _create_deployment(client, model_id, **overrides):
    body = {"model_id": model_id, **overrides}
    resp = client.post("/api/v1/deployments", json=body)
    assert resp.status_code == 201
    return resp.json()


# ── GET /api/v1/health ──────────────────────────────────────────────


class TestHealthEndpoint:
    """GET /api/v1/health"""

    def test_returns_healthy(self, test_client):
        resp = test_client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_includes_version(self, test_client):
        resp = test_client.get("/api/v1/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_uptime_is_positive(self, test_client):
        resp = test_client.get("/api/v1/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0

    def test_counts_registered_models(self, test_client):
        # Initially zero registered via native API
        data = test_client.get("/api/v1/health").json()
        assert data["models_registered"] == 0

        # Register a model
        _create_model(test_client)
        data = test_client.get("/api/v1/health").json()
        assert data["models_registered"] == 1

    def test_counts_routable_models(self, test_client):
        # YAML-loaded models should be counted as routable
        data = test_client.get("/api/v1/health").json()
        assert data["models_routable"] >= 1  # at least the YAML test models

    def test_counts_deployments(self, test_client):
        data = test_client.get("/api/v1/health").json()
        assert data["deployments_total"] == 0
        assert data["deployments_running"] == 0

        model = _create_model(test_client)
        _create_deployment(test_client, model["id"])
        data = test_client.get("/api/v1/health").json()
        assert data["deployments_total"] == 1
        assert data["deployments_running"] == 0  # still pending

    def test_backends_present(self, test_client):
        data = test_client.get("/api/v1/health").json()
        assert "backends" in data


# ── GET /api/v1/gpu-pools ───────────────────────────────────────────


class TestGpuPoolsEndpoint:
    """GET /api/v1/gpu-pools"""

    def test_empty_when_no_models(self, test_client):
        resp = test_client.get("/api/v1/gpu-pools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["data"] == []

    def test_pools_from_registered_models(self, test_client):
        _create_model(test_client, name="m1", required_gpu_sku="Standard_ND96asr_v4")
        _create_model(test_client, name="m2", required_gpu_sku="Standard_ND96asr_v4")
        _create_model(
            test_client, name="m3",
            required_gpu_sku="Standard_ND96isr_H100_v5",
            modality="embedding",
        )

        data = test_client.get("/api/v1/gpu-pools").json()
        assert data["count"] == 2
        skus = {p["gpu_sku"] for p in data["data"]}
        assert skus == {"Standard_ND96asr_v4", "Standard_ND96isr_H100_v5"}

        a100_pool = next(p for p in data["data"] if "asr" in p["gpu_sku"])
        assert a100_pool["models_registered"] == 2

    def test_gpu_allocation_from_running_deployments(self, test_client):
        model = _create_model(
            test_client, name="alloc-model",
            required_gpu_sku="Standard_ND96asr_v4",
            tp_degree=4,
        )
        dep = _create_deployment(
            test_client, model["id"],
            min_replicas=2, max_replicas=8,
        )

        # Transition to running
        test_client.patch(f"/api/v1/deployments/{dep['id']}", json={
            "status": "running",
            "endpoint_url": "http://alloc-model.directai.svc.cluster.local:8001",
        })

        data = test_client.get("/api/v1/gpu-pools").json()
        assert data["count"] == 1
        pool = data["data"][0]
        assert pool["gpu_sku"] == "Standard_ND96asr_v4"
        assert pool["deployments_running"] == 1
        # 2 min_replicas × 4 TP = 8 GPUs allocated
        assert pool["total_gpu_allocated"] == 8
        assert pool["min_replicas_sum"] == 2
        assert pool["max_replicas_sum"] == 8

    def test_pools_sorted_by_sku(self, test_client):
        _create_model(test_client, name="z-model", required_gpu_sku="Standard_Z")
        _create_model(test_client, name="a-model", required_gpu_sku="Standard_A")

        data = test_client.get("/api/v1/gpu-pools").json()
        skus = [p["gpu_sku"] for p in data["data"]]
        assert skus == sorted(skus)


# ── status_url on deployment responses ──────────────────────────────


class TestDeploymentStatusUrl:
    """Deployment responses include a pollable status_url."""

    def test_create_includes_status_url(self, test_client):
        model = _create_model(test_client, name="url-model")
        dep = _create_deployment(test_client, model["id"])
        assert "status_url" in dep
        assert dep["status_url"] == f"/api/v1/deployments/{dep['id']}"

    def test_get_includes_status_url(self, test_client):
        model = _create_model(test_client, name="url-get-model")
        dep = _create_deployment(test_client, model["id"])
        resp = test_client.get(f"/api/v1/deployments/{dep['id']}")
        data = resp.json()
        assert data["status_url"] == f"/api/v1/deployments/{dep['id']}"

    def test_list_includes_status_url(self, test_client):
        model = _create_model(test_client, name="url-list-model")
        _create_deployment(test_client, model["id"])
        resp = test_client.get("/api/v1/deployments")
        data = resp.json()
        assert data["count"] == 1
        assert data["data"][0]["status_url"].startswith("/api/v1/deployments/")

    def test_update_includes_status_url(self, test_client):
        model = _create_model(test_client, name="url-patch-model")
        dep = _create_deployment(test_client, model["id"])
        resp = test_client.patch(f"/api/v1/deployments/{dep['id']}", json={
            "status": "provisioning",
        })
        data = resp.json()
        assert data["status_url"] == f"/api/v1/deployments/{dep['id']}"

    def test_delete_includes_status_url(self, test_client):
        model = _create_model(test_client, name="url-del-model")
        dep = _create_deployment(test_client, model["id"])
        resp = test_client.delete(f"/api/v1/deployments/{dep['id']}")
        data = resp.json()
        assert data["status_url"] == f"/api/v1/deployments/{dep['id']}"
