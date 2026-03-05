"""
PostgreSQL-backed API key store with in-memory TTL cache.

Looks up SHA-256 hashed API keys in the ``api_keys`` table.  Results are
cached in-process for ``cache_ttl`` seconds to avoid per-request DB round
trips.  Revoked and missing keys are negative-cached with the same TTL.

Falls back gracefully: if ``database_url`` is empty/None the store is
disabled and ``validate`` always returns None (caller should fall through
to the legacy env-var check).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg  # type: ignore[import-untyped]
except ImportError:
    asyncpg = None  # type: ignore[assignment]


# ── Per-modality token pricing (USD per token) ─────────────────────
# Used to compute monthly spend for credit-cap enforcement.
MODALITY_PRICING: dict[str, tuple[float, float]] = {
    # (input_cost_per_token, output_cost_per_token)
    "chat": (0.10 / 1_000_000, 0.20 / 1_000_000),
    "embedding": (0.02 / 1_000_000, 0.0),
    "transcription": (0.0, 0.10 / 1_000_000),
}
_DEFAULT_PRICING = MODALITY_PRICING["chat"]


@dataclass(frozen=True)
class KeyInfo:
    """Validated API key metadata — returned on successful lookup."""

    key_id: str
    user_id: str
    name: str
    tier: str = "free"


@dataclass
class _CacheEntry:
    """TTL-wrapped cache entry (hit or negative-miss)."""

    value: Optional[KeyInfo]
    expires_at: float


@dataclass
class _SpendCacheEntry:
    """Cached monthly spend for a user (in cents)."""

    spend_cents: float
    expires_at: float


@dataclass
class PostgresKeyStore:
    """
    Async PostgreSQL key store with connection pooling + TTL cache.

    Usage::

        store = PostgresKeyStore(database_url="postgresql://...")
        await store.startup()
        info = await store.validate("dai_sk_abc123...")
        await store.shutdown()
    """

    database_url: str = ""
    cache_ttl: float = 60.0  # seconds
    spend_cache_ttl: float = 30.0  # seconds
    _pool: object = field(default=None, init=False, repr=False)
    _cache: dict[str, _CacheEntry] = field(default_factory=dict, init=False, repr=False)
    _spend_cache: dict[str, _SpendCacheEntry] = field(default_factory=dict, init=False, repr=False)

    @property
    def enabled(self) -> bool:
        return bool(self.database_url) and asyncpg is not None

    async def startup(self) -> None:
        if not self.enabled:
            logger.info("PostgresKeyStore disabled (no DATABASE_URL or asyncpg not installed)")
            return
        try:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=5.0,
            )
            logger.info("PostgresKeyStore connected (pool 2-10)")
        except Exception:
            logger.exception("PostgresKeyStore failed to connect — key validation will use env fallback")
            self._pool = None

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def validate(self, raw_key: str) -> Optional[KeyInfo]:
        """
        Validate a raw API key against the DB.

        Returns ``KeyInfo`` if the key exists and is not revoked,
        ``None`` if the key is invalid/revoked/not found,
        or ``None`` if the store is disabled.
        """
        if not self.enabled or self._pool is None:
            return None

        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        # ── Check cache ─────────────────────────────────────────
        now = time.monotonic()
        entry = self._cache.get(key_hash)
        if entry is not None and entry.expires_at > now:
            return entry.value

        # ── DB lookup ───────────────────────────────────────────
        try:
            row = await self._pool.fetchrow(
                """
                SELECT ak.id, ak.user_id, ak.name, ak.revoked_at,
                       COALESCE(u.tier, 'free') AS tier
                FROM api_keys ak
                LEFT JOIN users u ON u.id = ak.user_id
                WHERE ak.key_hash = $1
                """,
                key_hash,
            )
        except Exception:
            logger.exception("PostgresKeyStore query failed for hash=%s...", key_hash[:12])
            # On DB error, don't cache — let next request retry
            return None

        if row is None or row["revoked_at"] is not None:
            # Negative cache — key not found or revoked
            self._cache[key_hash] = _CacheEntry(value=None, expires_at=now + self.cache_ttl)
            return None

        info = KeyInfo(
            key_id=str(row["id"]),
            user_id=str(row["user_id"]),
            name=row["name"],
            tier=row["tier"],
        )
        self._cache[key_hash] = _CacheEntry(value=info, expires_at=now + self.cache_ttl)

        # Update last_used_at (fire-and-forget, don't block the request)
        try:
            await self._pool.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
                row["id"],
            )
        except Exception:
            pass  # Non-critical — best effort

        return info

    async def record_usage(
        self,
        *,
        user_id: str,
        api_key_id: str,
        model: str,
        modality: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Insert a usage record into the database."""
        if not self.enabled or self._pool is None:
            return
        try:
            await self._pool.execute(
                """
                INSERT INTO usage_records
                    (user_id, api_key_id, model, modality, input_tokens, output_tokens, request_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7::uuid)
                """,
                user_id,
                api_key_id,
                model,
                modality,
                input_tokens,
                output_tokens,
                request_id if request_id else None,
            )
        except Exception:
            logger.exception("Failed to record usage for user=%s model=%s", user_id, model)

    async def get_monthly_spend(self, user_id: str) -> float:
        """Return the user's current-month spend in cents.

        Uses a short-TTL cache to avoid per-request DB queries.
        Returns 0.0 if the store is disabled or on any error.
        """
        if not self.enabled or self._pool is None:
            return 0.0

        now = time.monotonic()
        entry = self._spend_cache.get(user_id)
        if entry is not None and entry.expires_at > now:
            return entry.spend_cents

        # Compute start of current month (UTC)
        utcnow = datetime.now(timezone.utc)
        month_start = utcnow.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        try:
            rows = await self._pool.fetch(
                """
                SELECT modality,
                       COALESCE(SUM(input_tokens), 0)::bigint  AS total_input,
                       COALESCE(SUM(output_tokens), 0)::bigint AS total_output
                FROM usage_records
                WHERE user_id = $1 AND created_at >= $2
                GROUP BY modality
                """,
                user_id,
                month_start,
            )
        except Exception:
            logger.exception("Failed to query monthly spend for user=%s", user_id)
            return 0.0

        # Compute cost in USD, convert to cents
        cost_usd = 0.0
        for row in rows:
            pricing = MODALITY_PRICING.get(row["modality"], _DEFAULT_PRICING)
            cost_usd += (
                row["total_input"] * pricing[0]
                + row["total_output"] * pricing[1]
            )
        spend_cents = cost_usd * 100.0

        self._spend_cache[user_id] = _SpendCacheEntry(
            spend_cents=spend_cents,
            expires_at=now + self.spend_cache_ttl,
        )
        return spend_cents
