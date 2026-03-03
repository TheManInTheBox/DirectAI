"""
Sensitive data audit tests.

Validates that API keys, user messages, audio content, and other PII
never leak into:
  - Structured log output
  - OTel span attributes
  - Error response bodies
  - Prometheus metric labels

Acceptance criteria for #27: "No sensitive data leaking."
"""

from __future__ import annotations

import io
import logging
from unittest.mock import patch

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

# ── Helpers ──────────────────────────────────────────────────────────

class _InMemoryExporter(SpanExporter):
    """Collects spans in memory for assertions."""

    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []

    def export(self, spans) -> SpanExportResult:
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self._spans)

    def shutdown(self) -> None:
        self._spans.clear()


SENSITIVE_API_KEY = "sk-live-super-secret-key-12345"
SENSITIVE_MESSAGE = "My social security number is 123-45-6789 and my password is hunter2"
SENSITIVE_EMBED_INPUT = "Encrypt my credit card 4111-1111-1111-1111 immediately"


# ── API Key Tests ────────────────────────────────────────────────────

class TestApiKeyNeverLeaked:
    """API keys must never appear in logs, spans, or error responses."""

    def test_invalid_key_error_does_not_contain_key(self, test_client):
        """401 response must not echo the attempted key back."""
        test_client.post(
            "/v1/chat/completions",
            json={"model": "test-chat", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": f"Bearer {SENSITIVE_API_KEY}"},
        )
        # Auth is disabled in test mode, so this will succeed (200/502).
        # Re-test with auth enabled.
        pass

    def test_invalid_key_not_in_401_body_with_auth_enabled(self, model_config_dir, monkeypatch):
        """With auth enabled, 401 body must not contain the key."""
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
        monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
        monkeypatch.setenv("DIRECTAI_API_KEYS", "valid-key-1,valid-key-2")

        from app.config import get_settings
        get_settings.cache_clear()

        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={"model": "test-chat", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": f"Bearer {SENSITIVE_API_KEY}"},
            )
            assert resp.status_code == 401
            body = resp.text
            assert SENSITIVE_API_KEY not in body
            # Ensure no partial key leakage either
            assert "super-secret" not in body

    def test_invalid_key_logged_only_as_hash(self, model_config_dir, monkeypatch, caplog):
        """Invalid key attempts should log only a sha256 prefix, never the raw key."""
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
        monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
        monkeypatch.setenv("DIRECTAI_API_KEYS", "valid-key-only")

        from app.config import get_settings
        get_settings.cache_clear()

        from fastapi.testclient import TestClient

        from app.main import app

        with caplog.at_level(logging.WARNING), TestClient(app, raise_server_exceptions=False) as client:
            client.post(
                "/v1/chat/completions",
                json={"model": "test-chat", "messages": [{"role": "user", "content": "hi"}]},
                headers={"Authorization": f"Bearer {SENSITIVE_API_KEY}"},
            )

        full_log = caplog.text
        assert SENSITIVE_API_KEY not in full_log
        assert "super-secret" not in full_log

    def test_valid_key_not_in_success_response(self, model_config_dir, monkeypatch):
        """Successful auth should not echo the key in response headers or body."""
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
        monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
        monkeypatch.setenv("DIRECTAI_API_KEYS", SENSITIVE_API_KEY)

        from app.config import get_settings
        get_settings.cache_clear()

        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/v1/models",
                headers={"Authorization": f"Bearer {SENSITIVE_API_KEY}"},
            )
            # Key must not appear in response body or headers
            assert SENSITIVE_API_KEY not in resp.text
            for header_val in resp.headers.values():
                assert SENSITIVE_API_KEY not in header_val


# ── Chat Message Tests ───────────────────────────────────────────────

class TestChatMessagesNeverLeaked:
    """User messages must not appear in logs or metric labels."""

    def test_message_content_not_in_access_log(self, test_client, caplog):
        """Request logging middleware must not log message bodies."""
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-chat",
                    "messages": [{"role": "user", "content": SENSITIVE_MESSAGE}],
                },
            )

        full_log = caplog.text
        assert "123-45-6789" not in full_log
        assert "hunter2" not in full_log
        assert "social security" not in full_log

    def test_message_not_in_metrics_labels(self, test_client):
        """Prometheus metrics must use model name, not message content, as labels."""
        # Make a request to populate metrics
        test_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-chat",
                "messages": [{"role": "user", "content": SENSITIVE_MESSAGE}],
            },
        )
        resp = test_client.get("/metrics")
        metrics_text = resp.text
        assert "123-45-6789" not in metrics_text
        assert "hunter2" not in metrics_text
        assert "social security" not in metrics_text


# ── Embedding Input Tests ────────────────────────────────────────────

class TestEmbeddingInputNeverLeaked:
    """Embedding input text must not appear in logs or metric labels."""

    def test_embedding_input_not_in_access_log(self, test_client, caplog):
        """Request logging middleware must not log embedding input."""
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/v1/embeddings",
                json={
                    "model": "test-embed",
                    "input": SENSITIVE_EMBED_INPUT,
                },
            )

        full_log = caplog.text
        assert "4111-1111-1111-1111" not in full_log
        assert "credit card" not in full_log

    def test_embedding_input_not_in_metrics(self, test_client):
        """Prometheus metrics must not contain embedding input text."""
        test_client.post(
            "/v1/embeddings",
            json={
                "model": "test-embed",
                "input": SENSITIVE_EMBED_INPUT,
            },
        )
        resp = test_client.get("/metrics")
        assert "4111-1111-1111-1111" not in resp.text


# ── Audio Transcription Tests ────────────────────────────────────────

class TestAudioContentNeverLeaked:
    """Audio file content must not appear in logs."""

    def test_audio_bytes_not_in_log(self, test_client, caplog):
        """Raw audio bytes must never be logged."""
        fake_audio = b"\x00\x01\x02\xff" * 100  # Fake binary audio
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/v1/audio/transcriptions",
                files={"file": ("test.wav", io.BytesIO(fake_audio), "audio/wav")},
                data={"model": "test-whisper"},
            )

        full_log = caplog.text
        # Binary content should not appear in log (even as repr)
        assert "\\x00\\x01\\x02\\xff" not in full_log

    def test_audio_filename_in_log_is_acceptable(self, test_client, caplog):
        """Filename may appear (not sensitive), but content must not."""
        with caplog.at_level(logging.DEBUG):
            test_client.post(
                "/v1/audio/transcriptions",
                files={"file": ("secret_meeting.wav", io.BytesIO(b"\x00" * 10), "audio/wav")},
                data={"model": "test-whisper"},
            )
        # Filenames in logs are acceptable, but audio content is not
        full_log = caplog.text
        assert "\\x00\\x00\\x00" not in full_log


# ── OTel Span Attribute Tests ────────────────────────────────────────

class TestSpanAttributesSanitised:
    """OTel spans must not contain message content or API keys."""

    def test_resolve_span_has_no_message_content(self, model_config_dir):
        """ModelRegistry.resolve span must contain model name, not messages."""
        from app.routing import ModelRegistry

        exporter = _InMemoryExporter()
        provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        try:
            with patch("app.telemetry.trace.get_tracer", return_value=provider.get_tracer("test")):
                registry = ModelRegistry.from_directory(model_config_dir)
                registry.resolve("test-chat")

            spans = exporter.get_finished_spans()
            for span in spans:
                if span.attributes:
                    for key, value in span.attributes.items():
                        str_value = str(value)
                        # Span attributes must not contain user content
                        assert "messages" not in key.lower() or "content" not in str(value).lower()
                        # Must not contain API keys
                        assert SENSITIVE_API_KEY not in str_value
        finally:
            provider.shutdown()

    def test_span_attributes_only_contain_allowed_fields(self, model_config_dir):
        """Verify that resolve spans only set expected attribute keys."""
        from app.routing import ModelRegistry

        exporter = _InMemoryExporter()
        provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        allowed_prefixes = {"directai.", "http.", "net.", "rpc.", "otel.", "service."}

        try:
            with patch("app.telemetry.trace.get_tracer", return_value=provider.get_tracer("test")):
                registry = ModelRegistry.from_directory(model_config_dir)
                registry.resolve("test-chat")

            spans = exporter.get_finished_spans()
            for span in spans:
                if span.attributes:
                    for key in span.attributes:
                        has_allowed_prefix = any(key.startswith(p) for p in allowed_prefixes)
                        assert has_allowed_prefix, (
                            f"Unexpected span attribute key '{key}' — could leak sensitive data. "
                            f"Only {allowed_prefixes} prefixes are allowed."
                        )
        finally:
            provider.shutdown()


# ── Error Response Tests ─────────────────────────────────────────────

class TestErrorResponsesSanitised:
    """Error responses must not leak internal details or sensitive input."""

    def test_404_model_does_not_echo_full_request(self, test_client):
        """404 for unknown model should not echo back user messages."""
        resp = test_client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": SENSITIVE_MESSAGE}],
            },
        )
        assert resp.status_code == 404
        body = resp.text
        assert "123-45-6789" not in body
        assert "hunter2" not in body

    def test_400_wrong_modality_does_not_echo_messages(self, test_client):
        """400 for wrong modality should not echo user messages."""
        resp = test_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-embed",  # embedding model, not chat
                "messages": [{"role": "user", "content": SENSITIVE_MESSAGE}],
            },
        )
        assert resp.status_code == 400
        body = resp.text
        assert "123-45-6789" not in body

    def test_embedding_404_does_not_echo_input(self, test_client):
        """404 for embedding should not echo input text."""
        resp = test_client.post(
            "/v1/embeddings",
            json={
                "model": "nonexistent",
                "input": SENSITIVE_EMBED_INPUT,
            },
        )
        assert resp.status_code == 404
        assert "4111-1111-1111-1111" not in resp.text


# ── Correlation ID Tests (not sensitive, but must be present) ────────

class TestCorrelationIdPresent:
    """Every response must have X-Request-ID — required for tracing."""

    def test_success_has_request_id(self, test_client):
        resp = test_client.get("/v1/models")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_error_has_request_id(self, test_client):
        resp = test_client.post(
            "/v1/chat/completions",
            json={"model": "nonexistent", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert "X-Request-ID" in resp.headers

    def test_client_request_id_preserved(self, test_client):
        custom_id = "my-trace-id-12345"
        resp = test_client.get(
            "/v1/models",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers["X-Request-ID"] == custom_id
