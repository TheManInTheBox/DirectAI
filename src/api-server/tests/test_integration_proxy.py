"""
Integration test — validates the full API server → backend proxy chain.

Spins up a lightweight mock inference backend (FastAPI) on a free port,
configures the API server to proxy to it via backendUrl in model YAML,
and exercises the complete request flow:

    TestClient (ASGI) → API server → BackendClient (real HTTP) → Mock server

This catches:
  - Model resolution failures
  - Broken proxy plumbing (headers, streaming, error translation)
  - Correlation ID propagation end-to-end
  - Modality gate enforcement
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════
# Mock Backend — mimics the TRT-LLM / ONNX Runtime engine HTTP surface
# ═══════════════════════════════════════════════════════════════════════

mock_app = FastAPI()

# Accumulator for assertions — cleared between tests
_received_requests: list[dict] = []


@mock_app.post("/v1/chat/completions")
async def mock_chat(request: Request):
    body = await request.json()
    _received_requests.append(
        {"path": "/v1/chat/completions", "body": body, "headers": dict(request.headers)}
    )

    if body.get("stream"):
        return _streaming_chat_response(body)
    return _non_streaming_chat_response(body)


def _non_streaming_chat_response(body: dict) -> JSONResponse:
    return JSONResponse(
        {
            "id": "chatcmpl-mock-001",
            "object": "chat.completion",
            "created": 1700000000,
            "model": body.get("model", "mock-chat"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello from mock backend!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )


def _streaming_chat_response(body: dict) -> StreamingResponse:
    model = body.get("model", "mock-chat")

    async def _stream():
        chunks = [
            {"delta": {"role": "assistant", "content": ""}, "finish_reason": None},
            {"delta": {"content": "Hello from mock!"}, "finish_reason": None},
            {"delta": {}, "finish_reason": "stop"},
        ]
        for chunk in chunks:
            payload = {
                "id": "chatcmpl-mock-001",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, **chunk}],
            }
            yield f"data: {json.dumps(payload)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@mock_app.post("/v1/embeddings")
async def mock_embeddings(request: Request):
    body = await request.json()
    _received_requests.append(
        {"path": "/v1/embeddings", "body": body, "headers": dict(request.headers)}
    )
    inputs = body.get("input", [])
    if isinstance(inputs, str):
        inputs = [inputs]

    return JSONResponse(
        {
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": [0.1, 0.2, 0.3]}
                for i in range(len(inputs))
            ],
            "model": body.get("model", "mock-embed"),
            "usage": {"prompt_tokens": len(inputs) * 3, "total_tokens": len(inputs) * 3},
        }
    )


@mock_app.post("/v1/audio/transcriptions")
async def mock_transcription(request: Request):
    # Multipart — read form data
    form = await request.form()
    _received_requests.append(
        {
            "path": "/v1/audio/transcriptions",
            "form_keys": list(form.keys()),
            "model": form.get("model"),
            "headers": dict(request.headers),
        }
    )
    return JSONResponse({"text": "Hello from mock transcription!"})


@mock_app.get("/healthz")
async def mock_healthz():
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════
# Server helpers
# ═══════════════════════════════════════════════════════════════════════


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_mock(app: FastAPI, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Block until the server is accepting connections
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
            if r.status_code == 200:
                return server, thread
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError(f"Mock server on port {port} never became ready")


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def mock_port():
    """Start mock backend once per module on a free port."""
    port = _free_port()
    server, thread = _start_mock(mock_app, port)
    yield port
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def _clear_requests():
    _received_requests.clear()
    yield
    _received_requests.clear()


@pytest.fixture()
def proxy_client(mock_port: int, tmp_path: Path, monkeypatch, _clear_requests):
    """
    API server TestClient → real HTTP → mock backend.

    Model configs use backendUrl to point at the mock.
    """
    chat_yaml = f"""\
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: mock-chat
spec:
  displayName: "Mock Chat Model"
  ownedBy: integration-test
  modality: chat
  engine:
    type: tensorrt-llm
    image: "test/trtllm:integration"
    backendUrl: "http://127.0.0.1:{mock_port}"
  hardware:
    gpuSku: Standard_ND96asr_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: always-warm
    minReplicas: 1
    maxReplicas: 1
    targetConcurrency: 4
  api:
    aliases:
      - mock-chat
      - integration/mock-chat
"""
    embed_yaml = f"""\
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: mock-embed
spec:
  displayName: "Mock Embedding Model"
  ownedBy: integration-test
  modality: embedding
  engine:
    type: onnxruntime
    image: "test/onnxrt:integration"
    backendUrl: "http://127.0.0.1:{mock_port}"
  hardware:
    gpuSku: Standard_NC24ads_A100_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: always-warm
    minReplicas: 1
    maxReplicas: 1
    targetConcurrency: 32
  api:
    aliases:
      - mock-embed
"""
    (tmp_path / "chat.yaml").write_text(chat_yaml)
    (tmp_path / "embed.yaml").write_text(embed_yaml)

    whisper_yaml = f"""\
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: mock-whisper
spec:
  displayName: "Mock Whisper"
  ownedBy: integration-test
  modality: transcription
  engine:
    type: tensorrt-llm
    image: "test/trtllm-whisper:integration"
    backendUrl: "http://127.0.0.1:{mock_port}"
  hardware:
    gpuSku: Standard_ND96asr_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: scale-to-zero
    minReplicas: 0
    maxReplicas: 1
    targetConcurrency: 4
  api:
    aliases:
      - mock-whisper
      - whisper-1
"""
    (tmp_path / "whisper.yaml").write_text(whisper_yaml)

    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("DIRECTAI_API_KEYS", "")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ═══════════════════════════════════════════════════════════════════════
# Chat completion proxy tests
# ═══════════════════════════════════════════════════════════════════════


class TestChatProxy:
    """Non-streaming and streaming chat proxied through the API server."""

    def test_non_streaming_round_trip(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "mock-chat", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello from mock backend!"
        assert data["usage"]["total_tokens"] == 15

    def test_streaming_round_trip(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={
                "model": "mock-chat",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            },
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        chunks = []
        for line in resp.text.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                chunks.append(json.loads(line[6:]))

        # Should have role + content + finish chunks
        assert len(chunks) == 3
        # Reconstruct assistant message from deltas
        content = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
        assert content == "Hello from mock!"
        # Last chunk should have finish_reason
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"

        # ── Streaming must update Prometheus metrics ────────────────
        metrics_resp = proxy_client.get("/metrics")
        assert metrics_resp.status_code == 200
        body = metrics_resp.text
        # Counter for completed requests
        assert 'directai_requests_total{method="chat",model="mock-chat",status="ok"}' in body
        # Histogram should have at least one observation
        assert 'directai_request_duration_seconds_count{method="chat",model="mock-chat"}' in body

    def test_alias_resolution(self, proxy_client: TestClient):
        """Both aliases route to the same backend."""
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "integration/mock-chat", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "Hello from mock backend!"

    def test_model_not_found_returns_404(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "does-not-exist", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 404

    def test_wrong_modality_returns_400(self, proxy_client: TestClient):
        """Sending chat request to an embedding model should fail."""
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "mock-embed", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 400
        assert "embedding" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# Embedding proxy tests
# ═══════════════════════════════════════════════════════════════════════


class TestEmbeddingProxy:
    """Embedding requests proxied through the API server."""

    def test_single_input(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/embeddings",
            json={"model": "mock-embed", "input": "Hello world"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert data["data"][0]["embedding"] == [0.1, 0.2, 0.3]

    def test_batch_input(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/embeddings",
            json={"model": "mock-embed", "input": ["Hello", "World", "Test"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 3
        for i, item in enumerate(data["data"]):
            assert item["index"] == i

    def test_wrong_modality_returns_400(self, proxy_client: TestClient):
        """Sending embedding request to a chat model should fail."""
        resp = proxy_client.post(
            "/v1/embeddings",
            json={"model": "mock-chat", "input": "Hello"},
        )
        assert resp.status_code == 400
        assert "chat" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# Correlation ID propagation
# ═══════════════════════════════════════════════════════════════════════


class TestCorrelationId:
    """X-Request-ID flows from client → API server → backend and back."""

    def test_client_id_propagated_to_backend(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "mock-chat", "messages": [{"role": "user", "content": "Hi"}]},
            headers={"X-Request-ID": "integ-test-id-42"},
        )
        assert resp.status_code == 200
        # API server should echo the ID back in the response
        assert resp.headers.get("x-request-id") == "integ-test-id-42"

        # Mock should have received it
        assert len(_received_requests) == 1
        backend_hdrs = _received_requests[0]["headers"]
        assert backend_hdrs.get("x-request-id") == "integ-test-id-42"

    def test_auto_generated_id_when_missing(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/chat/completions",
            json={"model": "mock-chat", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 200
        # Server should generate an ID even if the client didn't send one
        request_id = resp.headers.get("x-request-id")
        assert request_id is not None and len(request_id) > 0


# ═══════════════════════════════════════════════════════════════════════
# Backend error translation
# ═══════════════════════════════════════════════════════════════════════


class TestBackendErrors:
    """API server should translate backend failures to 502."""

    def test_unreachable_backend_returns_502(self, tmp_path: Path, monkeypatch):
        """Point at a port nothing is listening on → 502."""
        dead_port = _free_port()  # Nobody is listening here
        yaml_content = f"""\
apiVersion: directai/v1
kind: ModelDeployment
metadata:
  name: dead-backend
spec:
  displayName: "Dead Backend"
  ownedBy: test
  modality: chat
  engine:
    type: tensorrt-llm
    image: "test/dead:latest"
    backendUrl: "http://127.0.0.1:{dead_port}"
  hardware:
    gpuSku: Standard_ND96asr_v4
    gpuCount: 1
    nvmeCacheEnabled: false
  scaling:
    tier: always-warm
    minReplicas: 1
    maxReplicas: 1
    targetConcurrency: 4
  api:
    aliases:
      - dead-backend
"""
        (tmp_path / "dead.yaml").write_text(yaml_content)
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("DIRECTAI_API_KEYS", "")

        from app.config import get_settings

        get_settings.cache_clear()

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "dead-backend",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert resp.status_code == 502


# ═══════════════════════════════════════════════════════════════════════
# Audio transcription proxy tests
# ═══════════════════════════════════════════════════════════════════════

import io


class TestAudioProxy:
    """Multipart audio transcription proxied through the API server."""

    def test_transcription_round_trip(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={"model": "mock-whisper"},
            files={"file": ("test.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Hello from mock transcription!"

    def test_transcription_alias_whisper_1(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("audio.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["text"] == "Hello from mock transcription!"

    def test_transcription_model_not_found(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={"model": "nonexistent"},
            files={"file": ("test.wav", io.BytesIO(b"fake"), "audio/wav")},
        )
        assert resp.status_code == 404

    def test_transcription_wrong_modality(self, proxy_client: TestClient):
        """Sending transcription to a chat model should fail."""
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={"model": "mock-chat"},
            files={"file": ("test.wav", io.BytesIO(b"fake"), "audio/wav")},
        )
        assert resp.status_code == 400
        assert "chat" in resp.json()["detail"].lower()

    def test_transcription_forwards_optional_fields(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={
                "model": "mock-whisper",
                "language": "en",
                "temperature": "0.0",
                "response_format": "json",
            },
            files={"file": ("test.wav", io.BytesIO(b"fake-audio"), "audio/wav")},
        )
        assert resp.status_code == 200
        # Verify the backend received the form fields
        assert len(_received_requests) == 1
        assert _received_requests[0]["model"] == "mock-whisper"
        assert "language" in _received_requests[0]["form_keys"]

    def test_transcription_propagates_request_id(self, proxy_client: TestClient):
        resp = proxy_client.post(
            "/v1/audio/transcriptions",
            data={"model": "mock-whisper"},
            files={"file": ("test.wav", io.BytesIO(b"fake"), "audio/wav")},
            headers={"X-Request-ID": "audio-test-99"},
        )
        assert resp.status_code == 200
        assert len(_received_requests) == 1
        assert _received_requests[0]["headers"].get("x-request-id") == "audio-test-99"


# ═══════════════════════════════════════════════════════════════════════
# Health probes (still work with proxy wiring)
# ═══════════════════════════════════════════════════════════════════════


class TestHealthProbes:
    def test_liveness(self, proxy_client: TestClient):
        assert proxy_client.get("/healthz").status_code == 200

    def test_readiness_reports_model_count(self, proxy_client: TestClient):
        resp = proxy_client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["models"] == 3  # chat + embed + whisper

    def test_models_list_contains_all_aliases(self, proxy_client: TestClient):
        resp = proxy_client.get("/v1/models")
        assert resp.status_code == 200
        ids = {m["id"] for m in resp.json()["data"]}
        assert {"mock-chat", "integration/mock-chat", "mock-embed", "mock-whisper", "whisper-1"} <= ids
