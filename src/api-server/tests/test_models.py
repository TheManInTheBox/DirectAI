"""Tests for GET /v1/models."""


def test_list_models(test_client):
    response = test_client.get("/v1/models")
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "list"

    model_ids = {m["id"] for m in data["data"]}
    # All aliases from our test configs should be present
    assert "test-chat" in model_ids
    assert "org/test-chat" in model_ids
    assert "test-embed" in model_ids
    assert "test-whisper" in model_ids
    assert "whisper-1" in model_ids


def test_list_models_owned_by(test_client):
    response = test_client.get("/v1/models")
    data = response.json()

    for model in data["data"]:
        assert model["owned_by"] == "test"
        assert model["object"] == "model"
