"""
Audit logging module — tamper-proof request/response capture.

Every inference request produces a structured audit record written
asynchronously to PostgreSQL (queryable, 90-day retention) and
optionally to Azure Immutable Blob Storage (long-term archival).

Architecture:
  1. AuditMiddleware captures request/response data (non-blocking).
  2. AuditRecord is pushed onto an async queue.
  3. AuditWriter drains the queue in a background task, writing to
     PostgreSQL and (if configured) Blob Storage.

Zero latency impact on the request path — audit writes happen after
the response is sent to the client.
"""

from app.audit.middleware import AuditMiddleware
from app.audit.schemas import AuditRecord
from app.audit.writer import AuditWriter

__all__ = ["AuditMiddleware", "AuditRecord", "AuditWriter"]
