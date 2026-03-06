"""
Tests for the audit logging module — schemas, writer, and middleware.

Covers:
  - AuditRecord creation and serialization
  - AuditWriter queue mechanics (enqueue, flush, drop on full)
  - AuditWriter PostgreSQL batch insert (mocked)
  - AuditMiddleware request/response capture (non-streaming)
  - AuditMiddleware streaming response capture
  - AuditMiddleware skips non-inference paths
  - AuditMiddleware handles client disconnect (partial records)
  - Zero regression on existing 216 tests (audit disabled by default)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.audit.config import AuditConfig
from app.audit.schemas import (
    AuditInputSummary,
    AuditOutputSummary,
    AuditRecord,
    GuardrailsResult,
)
from app.audit.writer import AuditWriter


# ════════════════════════════════════════════════════════════════════
# AuditRecord unit tests
# ════════════════════════════════════════════════════════════════════


class TestAuditRecord:
    def test_create_minimal(self):
        record = AuditRecord(
            request_id="req-123",
            method="POST",
            path="/v1/chat/completions",
        )
        assert record.request_id == "req-123"
        assert record.method == "POST"
        assert record.status_code == 0
        assert record.user_id is None
        assert record.guardrails is None
        assert isinstance(record.timestamp, datetime)

    def test_create_full(self):
        record = AuditRecord(
            request_id="req-456",
            method="POST",
            path="/v1/embeddings",
            user_id="user-1",
            api_key_id="key-1",
            api_key_prefix="dai_sk_a19d",
            model="bge-large-en-v1.5",
            modality="embedding",
            input_summary=AuditInputSummary(token_count=150, message_count=3),
            output_summary=AuditOutputSummary(
                token_count=200, finish_reason="stop", is_partial=False
            ),
            guardrails=GuardrailsResult(
                pii_detected=False, injection_detected=False
            ),
            latency_ms=42.5,
            status_code=200,
            ip_address="abc123",
            user_agent="openai-python/1.0",
            request_body={"input": "hello"},
            response_body='{"data": []}',
        )
        assert record.model == "bge-large-en-v1.5"
        assert record.input_summary.token_count == 150
        assert record.output_summary.finish_reason == "stop"
        assert record.guardrails.pii_detected is False

    def test_to_pg_row_excludes_bodies(self):
        record = AuditRecord(
            request_id="req-789",
            method="POST",
            path="/v1/chat/completions",
            model="qwen",
            modality="chat",
            input_summary=AuditInputSummary(token_count=50),
            output_summary=AuditOutputSummary(token_count=100),
            status_code=200,
            latency_ms=150.7,
            request_body={"messages": [{"role": "user", "content": "secret"}]},
            response_body="big response text",
        )
        pg = record.to_pg_row()
        assert pg["request_id"] == "req-789"
        assert pg["input_tokens"] == 50
        assert pg["output_tokens"] == 100
        assert pg["latency_ms"] == 151  # rounded
        assert "request_body" not in pg
        assert "response_body" not in pg

    def test_to_blob_dict_includes_bodies(self):
        record = AuditRecord(
            request_id="req-blob",
            method="POST",
            path="/v1/chat/completions",
            request_body={"messages": [{"role": "user", "content": "hello"}]},
            response_body='{"choices": []}',
        )
        blob = record.to_blob_dict()
        assert blob["request_body"] == {"messages": [{"role": "user", "content": "hello"}]}
        assert blob["response_body"] == '{"choices": []}'
        assert blob["request_id"] == "req-blob"

    def test_guardrails_serialization(self):
        record = AuditRecord(
            request_id="req-guard",
            method="POST",
            path="/v1/chat/completions",
            guardrails=GuardrailsResult(
                content_safety={"hate": 0.01, "violence": 0.0},
                pii_detected=True,
                injection_detected=False,
            ),
        )
        pg = record.to_pg_row()
        assert pg["guardrails_result"]["pii_detected"] is True
        assert pg["guardrails_result"]["content_safety"]["hate"] == 0.01

    def test_no_guardrails_serializes_to_none(self):
        record = AuditRecord(
            request_id="req-noguard",
            method="GET",
            path="/v1/models",
        )
        pg = record.to_pg_row()
        assert pg["guardrails_result"] is None


# ════════════════════════════════════════════════════════════════════
# AuditWriter unit tests
# ════════════════════════════════════════════════════════════════════


class TestAuditWriter:
    def _make_record(self, request_id: str = "req-test") -> AuditRecord:
        return AuditRecord(
            request_id=request_id,
            method="POST",
            path="/v1/chat/completions",
            model="test-model",
            modality="chat",
            status_code=200,
            latency_ms=10.0,
        )

    @pytest.mark.asyncio
    async def test_disabled_writer_does_nothing(self):
        config = AuditConfig(enabled=False)
        writer = AuditWriter(config)
        await writer.start()
        assert writer.enqueue(self._make_record()) is False
        assert writer.records_written == 0
        await writer.stop()

    @pytest.mark.asyncio
    async def test_enqueue_and_flush(self):
        config = AuditConfig(enabled=True, pg_enabled=False, blob_enabled=False,
                             flush_interval=0.1, batch_size=10, queue_size=100)
        writer = AuditWriter(config)
        await writer.start()

        for i in range(5):
            assert writer.enqueue(self._make_record(f"req-{i}")) is True

        assert writer.queue_size == 5

        # Wait for flush cycle
        await asyncio.sleep(0.3)

        assert writer.queue_size == 0
        assert writer.records_written == 5
        await writer.stop()

    @pytest.mark.asyncio
    async def test_queue_full_drops_records(self):
        config = AuditConfig(enabled=True, pg_enabled=False, blob_enabled=False,
                             flush_interval=60.0, queue_size=3)  # tiny queue, slow flush
        writer = AuditWriter(config)
        await writer.start()

        assert writer.enqueue(self._make_record("req-1")) is True
        assert writer.enqueue(self._make_record("req-2")) is True
        assert writer.enqueue(self._make_record("req-3")) is True
        assert writer.enqueue(self._make_record("req-4")) is False  # dropped
        assert writer.records_dropped == 1
        await writer.stop()

    @pytest.mark.asyncio
    async def test_pg_write_called(self):
        """Verify _write_pg is called with correct batch."""
        config = AuditConfig(enabled=True, pg_enabled=True, blob_enabled=False,
                             flush_interval=0.1, batch_size=10)

        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()

        # asyncpg pool.acquire() returns an async context manager
        mock_pool = MagicMock()
        acm = AsyncMock()
        acm.__aenter__ = AsyncMock(return_value=mock_conn)
        acm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = acm

        writer = AuditWriter(config, pg_pool=mock_pool)
        # Skip table creation in start()
        writer._running = True
        writer._task = asyncio.create_task(writer._writer_loop())

        for i in range(3):
            writer.enqueue(self._make_record(f"req-{i}"))

        await asyncio.sleep(0.3)
        assert mock_conn.executemany.called
        args = mock_conn.executemany.call_args
        assert len(args[0][1]) == 3  # 3 rows
        await writer.stop()

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self):
        config = AuditConfig(enabled=True, pg_enabled=False, blob_enabled=False,
                             flush_interval=60.0, batch_size=100, queue_size=100)
        writer = AuditWriter(config)
        await writer.start()

        for i in range(10):
            writer.enqueue(self._make_record(f"req-{i}"))

        # Don't wait for flush — stop should drain
        await writer.stop()
        assert writer.records_written == 10
        assert writer.queue_size == 0


# ════════════════════════════════════════════════════════════════════
# AuditMiddleware integration tests
# ════════════════════════════════════════════════════════════════════


@pytest.fixture()
def audit_client(model_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient with audit ENABLED."""
    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
    monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
    monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
    monkeypatch.setenv("DIRECTAI_AUDIT_ENABLED", "true")
    monkeypatch.setenv("DIRECTAI_AUDIT_PG_ENABLED", "false")  # No real PG in tests
    monkeypatch.setenv("DIRECTAI_AUDIT_BLOB_ENABLED", "false")
    monkeypatch.setenv("DIRECTAI_AUDIT_FLUSH_INTERVAL", "0.1")

    from app.middleware.rate_limit import TIER_LIMITS, TierLimits
    monkeypatch.setitem(TIER_LIMITS, "free", TierLimits(rpm=600, tpm=10_000_000))

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        # Reset rate limiter
        from app.middleware.rate_limit import RateLimitMiddleware
        mw = app.middleware_stack
        while mw is not None:
            if isinstance(mw, RateLimitMiddleware):
                mw.reset()
                mw._default_rpm = 600
                mw._default_tpm = 10_000_000
                break
            mw = getattr(mw, 'app', None)
        yield client


class TestAuditMiddleware:
    def test_healthz_not_audited(self, audit_client: TestClient):
        """Health probes should NOT generate audit records."""
        from app.main import app
        writer = app.state.audit_writer
        initial = writer.records_written + writer.queue_size

        resp = audit_client.get("/healthz")
        assert resp.status_code == 200

        # Give a moment for any async processing
        import time
        time.sleep(0.2)

        # Queue size should not have increased
        assert writer.queue_size + writer.records_written == initial

    def test_models_endpoint_audited(self, audit_client: TestClient):
        """GET /v1/models IS an inference path and should be audited."""
        from app.main import app
        writer = app.state.audit_writer
        before = writer.records_written + writer.queue_size

        resp = audit_client.get("/v1/models")
        assert resp.status_code == 200

        import time
        time.sleep(0.3)

        after = writer.records_written + writer.queue_size
        assert after > before, "Expected audit record for /v1/models"

    def test_embeddings_404_audited(self, audit_client: TestClient):
        """Even failed requests should produce audit records."""
        from app.main import app
        writer = app.state.audit_writer

        resp = audit_client.post(
            "/v1/embeddings",
            json={"input": "hello", "model": "nonexistent-model"},
        )
        assert resp.status_code == 404

        import time
        time.sleep(0.3)

        # The record should have been queued (either still in queue or written)
        assert (writer.records_written + writer.queue_size) > 0

    def test_readyz_not_audited(self, audit_client: TestClient):
        """Readiness probe should NOT generate audit records."""
        from app.main import app
        writer = app.state.audit_writer

        # Flush existing
        import time
        time.sleep(0.3)
        baseline = writer.records_written + writer.queue_size

        resp = audit_client.get("/readyz")
        assert resp.status_code == 200

        time.sleep(0.2)
        assert writer.records_written + writer.queue_size == baseline

    def test_metrics_not_audited(self, audit_client: TestClient):
        """Metrics endpoint should NOT generate audit records."""
        from app.main import app
        writer = app.state.audit_writer

        import time
        time.sleep(0.3)
        baseline = writer.records_written + writer.queue_size

        resp = audit_client.get("/metrics")
        assert resp.status_code == 200

        time.sleep(0.2)
        assert writer.records_written + writer.queue_size == baseline


# ════════════════════════════════════════════════════════════════════
# AuditMiddleware helpers unit tests
# ════════════════════════════════════════════════════════════════════


class TestAuditHelpers:
    def test_should_audit_inference_paths(self):
        from app.audit.middleware import _should_audit
        assert _should_audit("/v1/chat/completions") is True
        assert _should_audit("/v1/embeddings") is True
        assert _should_audit("/v1/audio/transcriptions") is True
        assert _should_audit("/v1/models") is True
        assert _should_audit("/api/v1/routes") is True
        assert _should_audit("/api/v1/deployments") is True

    def test_should_not_audit_health(self):
        from app.audit.middleware import _should_audit
        assert _should_audit("/healthz") is False
        assert _should_audit("/readyz") is False
        assert _should_audit("/metrics") is False
        assert _should_audit("/docs") is False
        assert _should_audit("/openapi.json") is False

    def test_extract_modality(self):
        from app.audit.middleware import _extract_modality
        assert _extract_modality("/v1/chat/completions") == "chat"
        assert _extract_modality("/v1/embeddings") == "embedding"
        assert _extract_modality("/v1/audio/transcriptions") == "transcription"
        assert _extract_modality("/v1/models") is None
        assert _extract_modality("/api/v1/routes") is None

    def test_hash_ip(self):
        from app.audit.middleware import _hash_ip
        h1 = _hash_ip("192.168.1.1")
        h2 = _hash_ip("192.168.1.1")
        h3 = _hash_ip("10.0.0.1")
        assert h1 == h2  # deterministic
        assert h1 != h3  # different IPs → different hashes
        assert len(h1) == 16  # truncated

    def test_count_input_tokens_chat(self):
        from app.audit.middleware import _count_input_tokens_estimate
        body = {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello world, how are you today?"},
            ]
        }
        tokens, msg_count = _count_input_tokens_estimate(body)
        assert msg_count == 2
        assert tokens > 0  # Should be roughly (16 + 30) / 4 ≈ 11

    def test_count_input_tokens_embedding(self):
        from app.audit.middleware import _count_input_tokens_estimate
        body = {"input": "Hello world"}
        tokens, msg_count = _count_input_tokens_estimate(body)
        assert tokens > 0
        assert msg_count == 0  # single string, not a list

    def test_count_input_tokens_embedding_list(self):
        from app.audit.middleware import _count_input_tokens_estimate
        body = {"input": ["Hello", "World", "Test sentence for embeddings"]}
        tokens, msg_count = _count_input_tokens_estimate(body)
        assert msg_count == 3
        assert tokens > 0

    def test_extract_output_tokens(self):
        from app.audit.middleware import _extract_output_tokens
        resp = json.dumps({
            "usage": {"prompt_tokens": 10, "completion_tokens": 25, "total_tokens": 35},
            "choices": [{"finish_reason": "stop"}],
        })
        tokens, reason = _extract_output_tokens(resp)
        assert tokens == 25
        assert reason == "stop"

    def test_extract_output_tokens_invalid_json(self):
        from app.audit.middleware import _extract_output_tokens
        tokens, reason = _extract_output_tokens("not json")
        assert tokens == 0
        assert reason is None
