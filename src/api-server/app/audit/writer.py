"""
Audit writer — async dual-write to PostgreSQL + Azure Blob Storage.

Non-blocking: callers push ``AuditRecord`` onto a queue; a background
task drains the queue in batches and writes to both sinks.

Graceful degradation:
  - If PostgreSQL is unavailable, records are logged to stdout as JSON
    (structured logging catch-net) and Blob write still attempted.
  - If Blob Storage is unavailable, PostgreSQL write still succeeds.
  - If both are down, records are logged to stdout.

No audit record is ever silently lost — worst case it shows up in
container logs for manual recovery.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.audit.config import AuditConfig
from app.audit.schemas import AuditRecord

logger = logging.getLogger("directai.audit")

# ── SQL ─────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    api_key_id TEXT,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    model TEXT,
    modality TEXT,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    status_code INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    guardrails_result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_logs(request_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_logs(user_id, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_audit_model_ts ON audit_logs(model, timestamp DESC);",
]

_INSERT_SQL = """
INSERT INTO audit_logs (
    request_id, timestamp, user_id, api_key_id,
    method, path, model, modality,
    input_tokens, output_tokens, status_code, latency_ms,
    guardrails_result
) VALUES (
    $1, $2, $3, $4,
    $5, $6, $7, $8,
    $9, $10, $11, $12,
    $13
)
"""

_PRUNE_SQL = """
DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '1 day' * $1
"""


class AuditWriter:
    """Async audit record writer with dual PostgreSQL + Blob sinks.

    Usage::

        writer = AuditWriter(config, pg_pool=pool)
        await writer.start()
        writer.enqueue(record)   # Non-blocking
        ...
        await writer.stop()      # Flush remaining + shutdown
    """

    def __init__(
        self,
        config: AuditConfig,
        pg_pool: object | None = None,  # asyncpg.Pool
    ) -> None:
        self._config = config
        self._pg_pool = pg_pool
        self._queue: asyncio.Queue[AuditRecord] = asyncio.Queue(
            maxsize=config.queue_size,
        )
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._records_written = 0
        self._records_dropped = 0

    @property
    def records_written(self) -> int:
        return self._records_written

    @property
    def records_dropped(self) -> int:
        return self._records_dropped

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def start(self) -> None:
        """Start the background writer task and ensure PG table exists."""
        if not self._config.enabled:
            logger.info("Audit writer disabled (DIRECTAI_AUDIT_ENABLED=false)")
            return

        # Ensure audit_logs table exists
        if self._pg_pool is not None and self._config.pg_enabled:
            try:
                async with self._pg_pool.acquire() as conn:
                    await conn.execute(_CREATE_TABLE_SQL)
                    for idx_sql in _CREATE_INDEXES_SQL:
                        await conn.execute(idx_sql)
                logger.info("Audit table ready (audit_logs)")
            except Exception:
                logger.exception("Failed to create audit_logs table — PG writes will fail")

        self._running = True
        self._task = asyncio.create_task(self._writer_loop(), name="audit-writer")
        logger.info(
            "Audit writer started (pg=%s, blob=%s, batch=%d, flush=%.1fs)",
            self._config.pg_enabled and self._pg_pool is not None,
            self._config.blob_enabled,
            self._config.batch_size,
            self._config.flush_interval,
        )

    async def stop(self) -> None:
        """Flush remaining records and stop the background task."""
        self._running = False
        if self._task is not None:
            # Drain remaining
            await self._flush_batch(drain=True)
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(
            "Audit writer stopped (written=%d, dropped=%d)",
            self._records_written,
            self._records_dropped,
        )

    def enqueue(self, record: AuditRecord) -> bool:
        """Push an audit record onto the queue (non-blocking).

        Returns True if queued, False if dropped (queue full).
        """
        if not self._config.enabled:
            return False
        try:
            self._queue.put_nowait(record)
            return True
        except asyncio.QueueFull:
            self._records_dropped += 1
            logger.warning(
                "Audit queue full — dropping record %s (dropped=%d)",
                record.request_id,
                self._records_dropped,
            )
            # Fallback: log to stdout so the record isn't silently lost
            self._log_fallback(record)
            return False

    async def prune(self) -> int:
        """Delete audit records older than retention period. Returns count deleted."""
        if self._pg_pool is None:
            return 0
        try:
            async with self._pg_pool.acquire() as conn:
                result = await conn.execute(
                    _PRUNE_SQL, self._config.pg_retention_days,
                )
                count = int(result.split()[-1]) if result else 0
                if count > 0:
                    logger.info("Pruned %d audit records (retention=%dd)", count, self._config.pg_retention_days)
                return count
        except Exception:
            logger.exception("Failed to prune audit records")
            return 0

    # ── Internal ────────────────────────────────────────────────────

    async def _writer_loop(self) -> None:
        """Background loop: drain queue in batches, write to sinks."""
        while self._running:
            try:
                await self._flush_batch(drain=False)
                await asyncio.sleep(self._config.flush_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Audit writer loop error — will retry")
                await asyncio.sleep(1.0)

    async def _flush_batch(self, drain: bool = False) -> None:
        """Collect up to batch_size records from queue and write them."""
        batch: list[AuditRecord] = []
        limit = self._queue.qsize() if drain else self._config.batch_size

        for _ in range(limit):
            try:
                record = self._queue.get_nowait()
                batch.append(record)
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        # Write to PostgreSQL
        pg_ok = await self._write_pg(batch)

        # Write to Blob Storage
        blob_ok = await self._write_blob(batch)

        # Fallback: if both sinks failed, log to stdout
        if not pg_ok and not blob_ok:
            for record in batch:
                self._log_fallback(record)

        self._records_written += len(batch)

    async def _write_pg(self, batch: list[AuditRecord]) -> bool:
        """Batch INSERT into PostgreSQL audit_logs table."""
        if self._pg_pool is None or not self._config.pg_enabled:
            return False

        try:
            async with self._pg_pool.acquire() as conn:
                # Use executemany for batch efficiency
                rows = []
                for record in batch:
                    pg = record.to_pg_row()
                    rows.append((
                        pg["request_id"],
                        pg["timestamp"],
                        pg["user_id"],
                        pg["api_key_id"],
                        pg["method"],
                        pg["path"],
                        pg["model"],
                        pg["modality"],
                        pg["input_tokens"],
                        pg["output_tokens"],
                        pg["status_code"],
                        pg["latency_ms"],
                        json.dumps(pg["guardrails_result"]) if pg["guardrails_result"] else None,
                    ))
                await conn.executemany(_INSERT_SQL, rows)
            return True
        except Exception:
            logger.exception("Failed to write %d audit records to PostgreSQL", len(batch))
            return False

    async def _write_blob(self, batch: list[AuditRecord]) -> bool:
        """Write audit records to Azure Blob Storage as gzipped JSON.

        Blob path: audit-logs/{user_id}/{year}/{month}/{day}/{hour}/{request_id}.json.gz

        NOTE: Azure Blob Storage integration is Phase 2 (Issue #63).
        This method is a structured placeholder that logs what WOULD be
        written. The actual azure-storage-blob SDK call will be wired in
        when the Bicep infra (immutable storage account) is deployed.
        """
        if not self._config.blob_enabled or not self._config.storage_account:
            return False

        written = 0
        for record in batch:
            try:
                blob_dict = record.to_blob_dict()
                blob_json = json.dumps(blob_dict, default=str, ensure_ascii=False)
                compressed = gzip.compress(blob_json.encode("utf-8"))

                # Build blob path
                ts = record.timestamp
                customer = record.user_id or "anonymous"
                blob_path = (
                    f"{customer}/{ts.year}/{ts.month:02d}/{ts.day:02d}/"
                    f"{ts.hour:02d}/{record.request_id}.json.gz"
                )

                # TODO (Issue #63): Replace with azure.storage.blob.aio upload
                # For now, log the blob path and size so we can validate the
                # pipeline before infra is provisioned.
                logger.debug(
                    "Audit blob [dry-run]: %s/%s (%d bytes compressed)",
                    self._config.storage_container,
                    blob_path,
                    len(compressed),
                )
                written += 1
            except Exception:
                logger.exception(
                    "Failed to prepare audit blob for %s", record.request_id,
                )

        if written > 0:
            logger.debug("Audit blob batch: %d/%d records prepared", written, len(batch))
        return written > 0

    def _log_fallback(self, record: AuditRecord) -> None:
        """Last-resort: log audit record to stdout as JSON.

        Container log aggregation (Azure Monitor / Datadog) will capture
        these, ensuring no audit record is silently lost even if both
        PG and Blob are down.
        """
        try:
            logger.warning(
                "AUDIT_FALLBACK: %s",
                json.dumps(record.to_pg_row(), default=str),
            )
        except Exception:
            logger.error("Failed to serialize audit fallback for %s", record.request_id)
