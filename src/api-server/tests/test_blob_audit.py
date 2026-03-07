"""
Tests for Azure Blob Storage audit sink (Issue #63) and PII redaction (Issue #65).

Covers:
  - Real blob upload path (BlobServiceClient mocked)
  - Blob path construction: {user_id}/{year}/{mm}/{dd}/{hh}/{request_id}.json.gz
  - Gzip-compressed JSON payload
  - PII redaction: IP, user-agent, api_key_prefix, message content, embeddings input
  - Redaction of multi-part (vision) content
  - Redaction off → full content preserved in blob
  - Blob client init failure → graceful degradation (PG still works)
  - Blob upload failure per-record → partial success counted
  - Stop() closes blob client
  - Writer with blob enabled but no connection string → blob writes skipped
"""

from __future__ import annotations

import asyncio
import gzip
import json
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audit.config import AuditConfig
from app.audit.redaction import (
    _REDACTED,
    redact_blob_dict,
    redact_message_content,
    redact_text,
)
from app.audit.schemas import (
    AuditInputSummary,
    AuditOutputSummary,
    AuditRecord,
    GuardrailsResult,
)
from app.audit.writer import AuditWriter


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


def _make_record(
    request_id: str = "req-blob-test",
    user_id: str = "user-42",
    **kwargs,
) -> AuditRecord:
    defaults = dict(
        request_id=request_id,
        method="POST",
        path="/v1/chat/completions",
        model="qwen2.5-3b-instruct",
        modality="chat",
        user_id=user_id,
        api_key_id="key-1",
        api_key_prefix="dai_sk_a19d",
        ip_address="hashed-ip-abc",
        user_agent="openai-python/1.40.0",
        input_summary=AuditInputSummary(token_count=50, message_count=2),
        output_summary=AuditOutputSummary(token_count=100, finish_reason="stop"),
        status_code=200,
        latency_ms=42.0,
        request_body={
            "model": "qwen2.5-3b-instruct",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is 2+2?"},
            ],
        },
        response_body='{"choices": [{"message": {"content": "4"}}]}',
    )
    defaults.update(kwargs)
    return AuditRecord(**defaults)


def _mock_blob_service():
    """Create a mock BlobServiceClient that returns a mock ContainerClient."""
    mock_blob_client = AsyncMock()
    mock_blob_client.upload_blob = AsyncMock()
    mock_blob_client.close = AsyncMock()

    mock_container_client = AsyncMock()
    mock_container_client.get_blob_client = MagicMock(return_value=mock_blob_client)
    mock_container_client.close = AsyncMock()

    mock_service = MagicMock()
    mock_service.get_container_client = MagicMock(return_value=mock_container_client)

    return mock_service, mock_container_client, mock_blob_client


# ════════════════════════════════════════════════════════════════════
# Redaction unit tests (Issue #65)
# ════════════════════════════════════════════════════════════════════


class TestRedaction:
    def test_redact_text_email(self):
        assert "[REDACTED]" in redact_text("Contact user@example.com for details")

    def test_redact_text_phone(self):
        assert "[REDACTED]" in redact_text("Call me at +1 555-123-4567")

    def test_redact_text_ssn(self):
        assert "[REDACTED]" in redact_text("SSN: 123-45-6789")

    def test_redact_text_no_pii(self):
        text = "Hello world, this is a test."
        assert redact_text(text) == text

    def test_redact_message_content_simple(self):
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is my SSN?"},
        ]
        result = redact_message_content(msgs)
        assert result[0]["content"] == _REDACTED
        assert result[1]["content"] == _REDACTED
        assert result[0]["role"] == "system"  # Role preserved
        assert result[1]["role"] == "user"

    def test_redact_message_content_multipart(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                ],
            }
        ]
        result = redact_message_content(msgs)
        assert result[0]["content"][0]["text"] == _REDACTED
        assert result[0]["content"][1]["image_url"]["url"] == _REDACTED

    def test_redact_message_content_none(self):
        msgs = [{"role": "assistant", "content": None}]
        result = redact_message_content(msgs)
        assert result[0]["content"] is None

    def test_redact_blob_dict_full(self):
        record = _make_record()
        blob = record.to_blob_dict()
        redacted = redact_blob_dict(blob)

        # PII fields scrubbed
        assert redacted["ip_address"] == _REDACTED
        assert redacted["user_agent"] == _REDACTED
        assert redacted["api_key_prefix"] == _REDACTED

        # Message content redacted
        assert redacted["request_body"]["messages"][0]["content"] == _REDACTED
        assert redacted["request_body"]["messages"][1]["content"] == _REDACTED

        # Response body redacted
        assert redacted["response_body"] == _REDACTED

        # Structural fields preserved
        assert redacted["request_id"] == "req-blob-test"
        assert redacted["model"] == "qwen2.5-3b-instruct"
        assert redacted["status_code"] == 200
        assert redacted["request_body"]["model"] == "qwen2.5-3b-instruct"

    def test_redact_blob_dict_embeddings_input_string(self):
        record = _make_record(
            path="/v1/embeddings",
            modality="embedding",
            request_body={"model": "bge-large", "input": "Hello world"},
            response_body=None,
        )
        blob = record.to_blob_dict()
        redacted = redact_blob_dict(blob)
        assert redacted["request_body"]["input"] == _REDACTED
        assert redacted["request_body"]["model"] == "bge-large"

    def test_redact_blob_dict_embeddings_input_list(self):
        record = _make_record(
            path="/v1/embeddings",
            modality="embedding",
            request_body={"model": "bge-large", "input": ["Hello", "World"]},
        )
        blob = record.to_blob_dict()
        redacted = redact_blob_dict(blob)
        assert redacted["request_body"]["input"] == [_REDACTED, _REDACTED]

    def test_redact_blob_dict_original_unchanged(self):
        """Redaction must NOT mutate the original dict (deep copy)."""
        record = _make_record()
        blob = record.to_blob_dict()
        original_ip = blob.get("ip_address")
        _ = redact_blob_dict(blob)
        assert blob.get("ip_address") == original_ip  # unchanged


# ════════════════════════════════════════════════════════════════════
# Blob writer integration tests (Issue #63)
# ════════════════════════════════════════════════════════════════════


class TestBlobWriter:
    @pytest.mark.asyncio
    async def test_blob_upload_called(self):
        """Verify blob upload is called for each record in batch."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=staudit;AccountKey=fake;EndpointSuffix=core.windows.net",
            storage_container="audit-logs",
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            for i in range(3):
                writer.enqueue(_make_record(request_id=f"req-{i}"))

            await asyncio.sleep(0.3)

            # 3 blobs should have been uploaded
            assert mock_container.get_blob_client.call_count == 3
            assert mock_blob.upload_blob.call_count == 3

            # Verify blob path format
            first_path = mock_container.get_blob_client.call_args_list[0][0][0]
            assert first_path.startswith("user-42/")
            assert first_path.endswith(".json.gz")

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_blob_upload_gzip_content(self):
        """Verify uploaded content is valid gzipped JSON."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            writer.enqueue(_make_record())
            await asyncio.sleep(0.3)

            # Extract uploaded data
            uploaded = mock_blob.upload_blob.call_args_list[0][0][0]
            decompressed = gzip.decompress(uploaded)
            data = json.loads(decompressed)

            assert data["request_id"] == "req-blob-test"
            assert data["model"] == "qwen2.5-3b-instruct"
            assert data["request_body"]["messages"][0]["role"] == "system"

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_blob_redaction_enabled(self):
        """When redact_pii=True, uploaded blob should have PII scrubbed."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            redact_pii=True,
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            writer.enqueue(_make_record())
            await asyncio.sleep(0.3)

            uploaded = mock_blob.upload_blob.call_args_list[0][0][0]
            data = json.loads(gzip.decompress(uploaded))

            # PII should be redacted
            assert data["ip_address"] == _REDACTED
            assert data["user_agent"] == _REDACTED
            assert data["api_key_prefix"] == _REDACTED
            assert data["request_body"]["messages"][0]["content"] == _REDACTED
            assert data["response_body"] == _REDACTED

            # Structural data preserved
            assert data["request_id"] == "req-blob-test"
            assert data["model"] == "qwen2.5-3b-instruct"
            assert data["status_code"] == 200

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_blob_redaction_disabled(self):
        """When redact_pii=False, full content should be in blob."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            redact_pii=False,
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            writer.enqueue(_make_record())
            await asyncio.sleep(0.3)

            uploaded = mock_blob.upload_blob.call_args_list[0][0][0]
            data = json.loads(gzip.decompress(uploaded))

            # Full content preserved
            assert data["ip_address"] == "hashed-ip-abc"
            assert data["user_agent"] == "openai-python/1.40.0"
            assert data["request_body"]["messages"][0]["content"] == "You are helpful."
            assert data["response_body"] == '{"choices": [{"message": {"content": "4"}}]}'

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_blob_no_connection_string_skips(self):
        """Blob enabled but no connection string → writes skipped."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="",  # No connection string
            flush_interval=0.1,
            batch_size=10,
        )
        writer = AuditWriter(config)
        await writer.start()

        writer.enqueue(_make_record())
        await asyncio.sleep(0.3)

        # Record should still be written (even if blob didn't work)
        assert writer.records_written == 1
        await writer.stop()

    @pytest.mark.asyncio
    async def test_blob_upload_failure_graceful(self):
        """Single blob upload failure shouldn't crash the batch."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()
        # First upload fails, second succeeds
        mock_blob.upload_blob = AsyncMock(
            side_effect=[Exception("network timeout"), None]
        )

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            writer.enqueue(_make_record(request_id="req-fail"))
            writer.enqueue(_make_record(request_id="req-ok"))

            await asyncio.sleep(0.3)

            # Both attempted
            assert mock_blob.upload_blob.call_count == 2

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_blob_path_anonymous_user(self):
        """Records without user_id use 'anonymous' in blob path."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            flush_interval=0.1,
            batch_size=10,
        )
        mock_service, mock_container, mock_blob = _mock_blob_service()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            writer.enqueue(_make_record(user_id=None))
            await asyncio.sleep(0.3)

            path = mock_container.get_blob_client.call_args_list[0][0][0]
            assert path.startswith("anonymous/")

            writer._running = False
            writer._task.cancel()
            try:
                await writer._task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_stop_closes_blob_client(self):
        """stop() should close the blob container client."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
            flush_interval=60.0,
            batch_size=10,
        )
        mock_container = AsyncMock()
        mock_container.close = AsyncMock()

        with patch("app.audit.writer.AuditWriter.start", new=AsyncMock()):
            writer = AuditWriter(config)
            writer._blob_container_client = mock_container
            writer._running = True
            writer._task = asyncio.create_task(writer._writer_loop())

            await writer.stop()
            mock_container.close.assert_called_once()
            assert writer._blob_container_client is None

    @pytest.mark.asyncio
    async def test_blob_init_failure_graceful(self):
        """If BlobServiceClient init fails, writer starts anyway (PG works)."""
        config = AuditConfig(
            enabled=True,
            pg_enabled=False,
            blob_enabled=True,
            storage_connection_string="invalid-connection-string",
            flush_interval=0.1,
            batch_size=10,
        )
        writer = AuditWriter(config)

        # Patch the deferred import inside writer.start()
        mock_bsc = MagicMock()
        mock_bsc.from_connection_string.side_effect = Exception("bad conn string")
        with patch.dict("sys.modules", {"azure.storage.blob.aio": MagicMock(BlobServiceClient=mock_bsc)}):
            await writer.start()

        # Writer should be running despite blob failure
        assert writer._running is True
        assert writer._blob_container_client is None

        writer.enqueue(_make_record())
        await asyncio.sleep(0.2)

        # Record still processed (blob write returns False, fallback fires)
        assert writer.records_written == 1
        await writer.stop()
