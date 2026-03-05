"""GET /v1/models — model listing tests."""

from __future__ import annotations

import httpx


class TestModelList:
    """GET /v1/models returns the registered model catalog."""

    def test_returns_200(self, api_client: httpx.Client) -> None:
        r = api_client.get("/v1/models")
        assert r.status_code == 200

    def test_response_is_openai_list(self, api_client: httpx.Client) -> None:
        body = api_client.get("/v1/models").json()
        assert body["object"] == "list"
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 2, "Expected at least 2 models (chat + embedding)"

    def test_each_model_has_required_fields(self, api_client: httpx.Client) -> None:
        body = api_client.get("/v1/models").json()
        for model in body["data"]:
            assert "id" in model
            assert "object" in model
            assert model["object"] == "model"
            assert "owned_by" in model
            assert "created" in model

    def test_embeddings_model_present(self, api_client: httpx.Client) -> None:
        body = api_client.get("/v1/models").json()
        ids = [m["id"] for m in body["data"]]
        assert "bge-large-en-v1.5" in ids, f"Expected bge-large-en-v1.5 in model list, got {ids}"

    def test_chat_model_present(self, api_client: httpx.Client) -> None:
        body = api_client.get("/v1/models").json()
        ids = [m["id"] for m in body["data"]]
        assert "qwen2.5-3b-instruct" in ids, f"Expected qwen2.5-3b-instruct in model list, got {ids}"

    def test_aliases_expand(self, api_client: httpx.Client) -> None:
        """Each alias should appear as a separate model entry."""
        body = api_client.get("/v1/models").json()
        ids = {m["id"] for m in body["data"]}
        # BGE should have both bare and namespaced alias
        assert "bge-large-en-v1.5" in ids
        assert "baai/bge-large-en-v1.5" in ids
