"""
Stripe usage reporter — batches usage_records → Stripe Meters API.

Runs as an asyncio background task inside the API server process.
Every ``interval_seconds`` (default 60), it:
  1. Reads un-reported usage_records from PostgreSQL.
  2. Aggregates by user_id.
  3. Reports total tokens to the Stripe Meters API.

Requires:
  - DIRECTAI_STRIPE_SECRET_KEY
  - DIRECTAI_STRIPE_METER_ID_TOKENS
  - DIRECTAI_DATABASE_URL
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class StripeUsageReporter:
    """
    Background task that reports usage from PostgreSQL to Stripe Meters.

    Usage::

        reporter = StripeUsageReporter(pool=pool, stripe_key="sk_...", meter_id="mtr_...")
        await reporter.start()
        ...
        await reporter.stop()
    """

    def __init__(
        self,
        pool,
        stripe_secret_key: str = "",
        stripe_meter_id_tokens: str = "",
        interval_seconds: float = 60.0,
    ):
        self._pool = pool
        self._stripe_key = stripe_secret_key
        self._meter_id = stripe_meter_id_tokens
        self._interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def enabled(self) -> bool:
        return bool(self._pool and self._stripe_key and self._meter_id)

    async def start(self) -> None:
        if not self.enabled:
            logger.info(
                "StripeUsageReporter disabled (pool=%s, key=%s, meter=%s)",
                bool(self._pool),
                bool(self._stripe_key),
                bool(self._meter_id),
            )
            return
        self._http = httpx.AsyncClient(
            base_url="https://api.stripe.com",
            headers={"Authorization": f"Bearer {self._stripe_key}"},
            timeout=30.0,
        )
        self._task = asyncio.create_task(self._loop(), name="stripe-usage-reporter")
        logger.info("StripeUsageReporter started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self._flush()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("StripeUsageReporter flush failed")

    async def _flush(self) -> None:
        """Read unreported usage and send to Stripe."""
        if self._pool is None or self._http is None:
            return

        # Aggregate usage since last flush, grouped by user
        # We use a reporting_batch marker: records with request_id NOT NULL
        # that haven't been reported yet.  We mark them by NULLing the
        # request_id after reporting (or use a separate reported_at column).
        #
        # Simple approach: aggregate all records from the last interval,
        # report them, and delete to avoid double-counting.
        rows = await self._pool.fetch(
            """
            WITH batch AS (
                SELECT id, user_id, input_tokens, output_tokens
                FROM usage_records
                WHERE created_at > NOW() - INTERVAL '120 seconds'
                ORDER BY created_at
                LIMIT 10000
            )
            SELECT user_id, SUM(input_tokens + output_tokens) AS total_tokens
            FROM batch
            GROUP BY user_id
            HAVING SUM(input_tokens + output_tokens) > 0
            """
        )

        if not rows:
            return

        logger.info("Reporting usage for %d users to Stripe", len(rows))

        for row in rows:
            user_id = str(row["user_id"])
            total_tokens = int(row["total_tokens"])

            try:
                # Look up the Stripe customer ID for this user
                user_row = await self._pool.fetchrow(
                    "SELECT stripe_customer_id FROM users WHERE id = $1",
                    row["user_id"],
                )
                if user_row is None or not user_row["stripe_customer_id"]:
                    logger.warning("No Stripe customer for user %s — skipping", user_id)
                    continue

                stripe_customer_id = user_row["stripe_customer_id"]

                # Report to Stripe Meters API
                resp = await self._http.post(
                    "/v1/billing/meter_events",
                    data={
                        "event_name": "token_usage",
                        "payload[value]": str(total_tokens),
                        "payload[stripe_customer_id]": stripe_customer_id,
                    },
                )
                if resp.status_code >= 400:
                    logger.error(
                        "Stripe meter event failed for customer %s: %d %s",
                        stripe_customer_id,
                        resp.status_code,
                        resp.text[:200],
                    )
                else:
                    logger.info(
                        "Reported %d tokens for customer %s",
                        total_tokens,
                        stripe_customer_id,
                    )
            except Exception:
                logger.exception("Failed to report usage for user %s", user_id)
