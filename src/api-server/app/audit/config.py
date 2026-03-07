"""
Audit logging configuration.

Audit-specific settings are embedded in the main ``Settings`` class
(``app/config.py``) under the ``DIRECTAI_AUDIT_`` prefix.  This module
re-exports a helper to extract the audit-relevant subset.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditConfig:
    """Extracted audit configuration — passed to AuditWriter at startup."""

    enabled: bool = False

    # PostgreSQL (reuses main DATABASE_URL connection)
    pg_enabled: bool = True
    pg_retention_days: int = 90

    # Azure Blob Storage
    blob_enabled: bool = False
    storage_account: str = ""
    storage_connection_string: str = ""   # Azure Storage connection string (from Key Vault)
    storage_container: str = "audit-logs"
    retention_days: int = 365

    # Redacted logging mode (Issue #65)
    redact_pii: bool = False  # When True, scrub PII from blob records before upload

    # Writer tuning
    queue_size: int = 50_000
    flush_interval: float = 5.0  # seconds — max wait before flushing batch
    batch_size: int = 100  # max records per flush
