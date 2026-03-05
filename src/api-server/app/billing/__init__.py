"""
Billing module — Stripe Meters usage reporting for hybrid pricing.

DirectAI uses hybrid billing: base fee + metered per-token usage for
Pro and Managed tiers.  Free-tier credit-cap enforcement is handled
separately in ``auth.api_key`` (spend check).  Enterprise pays a flat
management fee — no metering.

Architecture
------------
1. Route handlers call ``emit_usage_event()`` after each request with
   token counts and tier info.
2. Events are pushed onto an in-memory ``asyncio.Queue``.
3. ``StripeUsageReporter`` runs a background task that drains the queue
   every ``flush_interval`` seconds and batch-reports to the Stripe
   Meters API via ``POST /v1/billing/meter_events``.

Only **Pro** and **Managed** events are reported.  Free-tier and
Enterprise events are silently dropped.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Tiers that get metered ──────────────────────────────────────────
_METERED_TIERS = frozenset({"pro", "managed"})


# ── Meter event ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class MeterEvent:
    """A single usage event destined for Stripe Meters."""

    stripe_customer_id: str  # Stripe Customer ID (cus_xxx)
    event_name: str          # Stripe Meter event name
    value: int               # Token count (or centiseconds for transcription)
    timestamp: int           # Unix epoch seconds
    idempotency_key: str     # Request-scoped dedup key


# ── Event buffer (module-level queue) ───────────────────────────────

_event_queue: asyncio.Queue[MeterEvent] = asyncio.Queue(maxsize=100_000)


def emit_usage_event(
    *,
    tier: str,
    stripe_customer_id: str,
    event_name: str,
    value: int,
    idempotency_key: str,
) -> bool:
    """Push a usage event onto the buffer (non-blocking).

    Returns ``True`` if the event was queued, ``False`` if dropped
    (queue full or non-metered tier).

    Parameters
    ----------
    tier : str
        User's pricing tier.  Only ``'pro'`` and ``'managed'`` are metered.
    stripe_customer_id : str
        Stripe ``cus_xxx`` ID linked to the user.
    event_name : str
        Meter event name configured in Stripe (e.g. ``'chat_input_tokens'``).
    value : int
        Quantity to meter (tokens, centiseconds, etc.).  Must be > 0.
    idempotency_key : str
        Unique key for deduplication (e.g. ``'{request_id}:{modality}:{direction}'``).
    """
    if tier not in _METERED_TIERS:
        return False
    if value <= 0:
        return False
    if not stripe_customer_id or not event_name:
        logger.debug("Dropped meter event — missing customer_id or event_name")
        return False
    evt = MeterEvent(
        stripe_customer_id=stripe_customer_id,
        event_name=event_name,
        value=value,
        timestamp=int(time.time()),
        idempotency_key=idempotency_key,
    )
    try:
        _event_queue.put_nowait(evt)
        return True
    except asyncio.QueueFull:
        logger.warning("Meter event queue full — dropping event for %s", stripe_customer_id)
        return False


# ── Stripe Usage Reporter ───────────────────────────────────────────

class StripeUsageReporter:
    """Background worker that drains the meter event queue and reports
    to the Stripe Billing Meter Events API.

    Initialisation parameters come from ``Settings`` (DIRECTAI_ prefix).
    When ``stripe_secret_key`` is empty the reporter runs in **dry-run
    mode** — events are drained and logged but not sent to Stripe.
    This is the default for dev/staging.
    """

    def __init__(
        self,
        *,
        stripe_secret_key: str = "",
        flush_interval: float = 60.0,
    ) -> None:
        self._secret_key = stripe_secret_key
        self._flush_interval = flush_interval
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._total_reported: int = 0
        self._total_dropped: int = 0

    @property
    def enabled(self) -> bool:
        """True if Stripe credentials are configured."""
        return bool(self._secret_key)

    @property
    def dry_run(self) -> bool:
        """True if running without Stripe credentials (events logged, not sent)."""
        return not self._secret_key

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_reported": self._total_reported,
            "total_dropped": self._total_dropped,
            "queue_size": _event_queue.qsize(),
        }

    async def start(self) -> None:
        """Start the background flush loop."""
        if self.dry_run:
            logger.info(
                "StripeUsageReporter started in DRY-RUN mode "
                "(no DIRECTAI_STRIPE_SECRET_KEY). Events will be "
                "drained and logged but not sent to Stripe."
            )
        else:
            logger.info(
                "StripeUsageReporter started — reporting to Stripe every %.0fs",
                self._flush_interval,
            )
        self._task = asyncio.create_task(self._run(), name="stripe-usage-reporter")

    async def stop(self) -> None:
        """Cancel the background task and do a final flush."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final drain on shutdown
        await self._flush()
        logger.info(
            "StripeUsageReporter stopped (reported=%d, dropped=%d, remaining=%d)",
            self._total_reported,
            self._total_dropped,
            _event_queue.qsize(),
        )

    async def _run(self) -> None:
        """Periodic flush loop."""
        try:
            while True:
                await asyncio.sleep(self._flush_interval)
                await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self) -> None:
        """Drain the queue and send events to Stripe."""
        events: list[MeterEvent] = []
        while not _event_queue.empty():
            try:
                events.append(_event_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not events:
            return

        if self.dry_run:
            logger.info(
                "DRY-RUN: would report %d meter events to Stripe (total value=%d)",
                len(events),
                sum(e.value for e in events),
            )
            self._total_reported += len(events)
            return

        # ── Send to Stripe Meter Events API ─────────────────────────
        # Stripe Meter Events API accepts one event per call (no batch
        # endpoint yet). We use httpx (already a dep) for async HTTP.
        import httpx

        async with httpx.AsyncClient(
            base_url="https://api.stripe.com",
            headers={
                "Authorization": f"Bearer {self._secret_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=httpx.Timeout(10.0, connect=5.0),
        ) as client:
            for evt in events:
                try:
                    resp = await client.post(
                        "/v1/billing/meter_events",
                        data={
                            "event_name": evt.event_name,
                            "payload[stripe_customer_id]": evt.stripe_customer_id,
                            "payload[value]": str(evt.value),
                            "timestamp": str(evt.timestamp),
                        },
                        headers={
                            "Idempotency-Key": evt.idempotency_key,
                        },
                    )
                    if resp.status_code in (200, 201):
                        self._total_reported += 1
                    elif resp.status_code == 409:
                        # Idempotent replay — already recorded
                        self._total_reported += 1
                        logger.debug(
                            "Meter event already recorded (idempotent): %s",
                            evt.idempotency_key,
                        )
                    else:
                        self._total_dropped += 1
                        logger.warning(
                            "Stripe meter event failed (%d): %s — customer=%s value=%d",
                            resp.status_code,
                            resp.text[:200],
                            evt.stripe_customer_id,
                            evt.value,
                        )
                except Exception:
                    self._total_dropped += 1
                    logger.exception(
                        "Failed to send meter event for customer=%s",
                        evt.stripe_customer_id,
                    )

        if events:
            logger.info(
                "Flushed %d meter events to Stripe (reported=%d total)",
                len(events),
                self._total_reported,
            )
