"""
Tests for the pre-compiled engine cache.

Covers:
- Engine cache CRUD via API endpoints
- Cache key generation and determinism
- Lookup hit / miss scenarios
- Version-based lazy invalidation
- Upsert behaviour (re-register same key)
- Filtering by architecture / GPU SKU / version
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.repository import build_cache_key

# ── Helpers ─────────────────────────────────────────────────────────

def _register_engine(client: TestClient, **overrides) -> dict:
    """POST a test engine to /api/v1/engine-cache."""
    payload = {
        "architecture": "llama",
        "parameter_count": "70b",
        "quantization": "float16",
        "tp_degree": 2,
        "gpu_sku": "Standard_ND96asr_v4",
        "trtllm_version": "0.16.0",
        "engine_uri": "https://storage.blob.core.windows.net/engines/llama/70b/a100/engine/",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/engine-cache", json=payload)
    return resp


# ── Cache key ───────────────────────────────────────────────────────


class TestCacheKey:
    """build_cache_key determinism and format."""

    def test_format(self):
        key = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.16.0")
        assert key == "llama_70b_float16_tp2_Standard_ND96asr_v4_trtllm0.16.0"

    def test_different_tp_produces_different_key(self):
        k1 = build_cache_key("llama", "70b", "float16", 1, "Standard_ND96asr_v4", "0.16.0")
        k2 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.16.0")
        assert k1 != k2

    def test_different_version_produces_different_key(self):
        k1 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.16.0")
        k2 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.17.0")
        assert k1 != k2

    def test_different_gpu_sku_produces_different_key(self):
        k1 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.16.0")
        k2 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96isr_H100_v5", "0.16.0")
        assert k1 != k2

    def test_different_quantization_produces_different_key(self):
        k1 = build_cache_key("llama", "70b", "float16", 2, "Standard_ND96asr_v4", "0.16.0")
        k2 = build_cache_key("llama", "70b", "int8", 2, "Standard_ND96asr_v4", "0.16.0")
        assert k1 != k2


# ── CRUD ────────────────────────────────────────────────────────────


class TestEngineCacheCRUD:
    """Register, list, get, delete engine cache entries."""

    def test_register_engine(self, test_client: TestClient):
        resp = _register_engine(test_client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["architecture"] == "llama"
        assert data["parameter_count"] == "70b"
        assert data["gpu_sku"] == "Standard_ND96asr_v4"
        assert data["trtllm_version"] == "0.16.0"
        assert data["cache_key"] == "llama_70b_float16_tp2_Standard_ND96asr_v4_trtllm0.16.0"
        assert data["engine_uri"].startswith("https://")
        assert "id" in data
        assert "created_at" in data

    def test_list_empty(self, test_client: TestClient):
        resp = test_client.get("/api/v1/engine-cache")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_list_after_register(self, test_client: TestClient):
        _register_engine(test_client)
        _register_engine(test_client, architecture="qwen", parameter_count="7b",
                         engine_uri="https://storage.blob.core.windows.net/engines/qwen/7b/")
        resp = test_client.get("/api/v1/engine-cache")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_get_by_id(self, test_client: TestClient):
        entry = _register_engine(test_client).json()
        resp = test_client.get(f"/api/v1/engine-cache/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["cache_key"] == entry["cache_key"]

    def test_get_not_found(self, test_client: TestClient):
        resp = test_client.get("/api/v1/engine-cache/nonexistent-id")
        assert resp.status_code == 404

    def test_delete(self, test_client: TestClient):
        entry = _register_engine(test_client).json()
        resp = test_client.delete(f"/api/v1/engine-cache/{entry['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == entry["id"]
        # Verify it's gone
        resp2 = test_client.get(f"/api/v1/engine-cache/{entry['id']}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, test_client: TestClient):
        resp = test_client.delete("/api/v1/engine-cache/nonexistent-id")
        assert resp.status_code == 404


# ── Lookup ──────────────────────────────────────────────────────────


class TestEngineCacheLookup:
    """Cache hit/miss and lazy invalidation."""

    def test_lookup_hit(self, test_client: TestClient):
        _register_engine(test_client)
        resp = test_client.get("/api/v1/engine-cache/lookup", params={
            "architecture": "llama",
            "parameter_count": "70b",
            "quantization": "float16",
            "tp_degree": 2,
            "gpu_sku": "Standard_ND96asr_v4",
            "trtllm_version": "0.16.0",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_hit"] is True
        assert data["entry"] is not None
        assert data["entry"]["architecture"] == "llama"

    def test_lookup_miss_no_entry(self, test_client: TestClient):
        resp = test_client.get("/api/v1/engine-cache/lookup", params={
            "architecture": "nonexistent",
            "parameter_count": "7b",
            "quantization": "float16",
            "tp_degree": 1,
            "gpu_sku": "Standard_ND96asr_v4",
            "trtllm_version": "0.16.0",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_hit"] is False
        assert data["entry"] is None

    def test_lookup_miss_version_mismatch(self, test_client: TestClient):
        """Lazy invalidation: stored version != requested version → miss."""
        _register_engine(test_client, trtllm_version="0.16.0")
        resp = test_client.get("/api/v1/engine-cache/lookup", params={
            "architecture": "llama",
            "parameter_count": "70b",
            "quantization": "float16",
            "tp_degree": 2,
            "gpu_sku": "Standard_ND96asr_v4",
            "trtllm_version": "0.17.0",  # different version → miss
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_hit"] is False
        assert data["entry"] is None

    def test_lookup_returns_cache_key(self, test_client: TestClient):
        resp = test_client.get("/api/v1/engine-cache/lookup", params={
            "architecture": "whisper",
            "parameter_count": "large-v3",
            "quantization": "float16",
            "tp_degree": 1,
            "gpu_sku": "Standard_ND96asr_v4",
            "trtllm_version": "0.16.0",
        })
        data = resp.json()
        expected = "whisper_large-v3_float16_tp1_Standard_ND96asr_v4_trtllm0.16.0"
        assert data["cache_key"] == expected


# ── Upsert ──────────────────────────────────────────────────────────


class TestEngineCacheUpsert:
    """Re-registering the same cache key updates engine_uri."""

    def test_upsert_updates_uri(self, test_client: TestClient):
        resp1 = _register_engine(test_client, engine_uri="https://old-uri/")
        assert resp1.status_code == 201
        old_id = resp1.json()["id"]

        resp2 = _register_engine(test_client, engine_uri="https://new-uri/")
        assert resp2.status_code == 201
        # Same ID (updated, not a new row)
        assert resp2.json()["id"] == old_id
        assert resp2.json()["engine_uri"] == "https://new-uri/"

    def test_upsert_does_not_duplicate(self, test_client: TestClient):
        _register_engine(test_client, engine_uri="https://uri-1/")
        _register_engine(test_client, engine_uri="https://uri-2/")
        resp = test_client.get("/api/v1/engine-cache")
        assert resp.json()["count"] == 1


# ── Filtering ───────────────────────────────────────────────────────


class TestEngineCacheFiltering:
    """List endpoint filtering."""

    def _seed(self, client: TestClient):
        _register_engine(client, architecture="llama", parameter_count="7b",
                         gpu_sku="Standard_ND96asr_v4",
                         engine_uri="https://s/llama-7b-a100/")
        _register_engine(client, architecture="llama", parameter_count="7b",
                         gpu_sku="Standard_ND96isr_H100_v5",
                         engine_uri="https://s/llama-7b-h100/")
        _register_engine(client, architecture="qwen", parameter_count="14b",
                         gpu_sku="Standard_ND96asr_v4",
                         engine_uri="https://s/qwen-14b-a100/")

    def test_filter_by_architecture(self, test_client: TestClient):
        self._seed(test_client)
        resp = test_client.get("/api/v1/engine-cache", params={"architecture": "llama"})
        assert resp.json()["count"] == 2

    def test_filter_by_gpu_sku(self, test_client: TestClient):
        self._seed(test_client)
        resp = test_client.get("/api/v1/engine-cache", params={"gpu_sku": "Standard_ND96isr_H100_v5"})
        assert resp.json()["count"] == 1

    def test_filter_by_version(self, test_client: TestClient):
        self._seed(test_client)
        resp = test_client.get("/api/v1/engine-cache", params={"trtllm_version": "0.16.0"})
        assert resp.json()["count"] == 3


# ── Version Invalidation ───────────────────────────────────────────


class TestVersionInvalidation:
    """DELETE /api/v1/engine-cache/version/{version}."""

    def test_invalidate_by_version(self, test_client: TestClient):
        _register_engine(test_client, trtllm_version="0.15.0",
                         engine_uri="https://old-engine/")
        _register_engine(test_client, architecture="qwen", parameter_count="7b",
                         trtllm_version="0.16.0",
                         engine_uri="https://new-engine/")
        # Invalidate the old version
        resp = test_client.delete("/api/v1/engine-cache/version/0.15.0")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1
        # Only 0.16.0 entry remains
        resp2 = test_client.get("/api/v1/engine-cache")
        assert resp2.json()["count"] == 1
        assert resp2.json()["data"][0]["trtllm_version"] == "0.16.0"

    def test_invalidate_nonexistent_version(self, test_client: TestClient):
        resp = test_client.delete("/api/v1/engine-cache/version/99.99.99")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0
