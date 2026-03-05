"""
Billing module — usage tracking for analytics (no Stripe metering).

DirectAI uses flat management-fee pricing ($3K/mo Managed, custom Enterprise).
Token-based Stripe Meters billing has been removed. The usage_records table
is still populated by the rate-limit middleware for dashboard analytics and
capacity planning, but nothing is reported to Stripe.

The StripeUsageReporter class is retained as a no-op stub so existing
startup/shutdown code doesn't need to be ripped out. It logs a message
and does nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StripeUsageReporter:
    """
    No-op stub — token metering to Stripe Meters API has been removed.

    DirectAI now charges flat management fees. Usage data is still recorded
    in PostgreSQL for dashboard analytics but is NOT reported to Stripe.

    This stub preserves the start/stop interface so the lifespan code in
    main.py doesn't need changes.
    """

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        pass

    @property
    def enabled(self) -> bool:
        return False

    async def start(self) -> None:
        logger.info(
            "StripeUsageReporter is a no-op — flat management-fee pricing, "
            "no token metering to Stripe."
        )

    async def stop(self) -> None:
        pass
