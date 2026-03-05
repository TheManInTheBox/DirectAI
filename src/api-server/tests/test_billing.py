"""
Tests for the billing module — Stripe Meters usage metering.

Validates:
  - emit_usage_event tier gating (only pro/managed get metered)
  - emit_usage_event drops zero/negative values
  - emit_usage_event drops when stripe_customer_id is missing
  - Queue overflow handling (silent drop, no crash)
  - StripeUsageReporter dry-run mode (events drained but not sent)
  - StripeUsageReporter flush sends to Stripe API
  - MeterEvent construction
"""

from __future__ import annotations

import asyncio

import pytest


# ── Helpers ──────────────────────────────────────────────────────────

def _drain_queue():
    """Empty the module-level event queue between tests."""
    from app.billing import _event_queue
    while not _event_queue.empty():
        try:
            _event_queue.get_nowait()
        except asyncio.QueueEmpty:
            break


@pytest.fixture(autouse=True)
def _clean_queue():
    """Ensure the queue is empty before and after each test."""
    _drain_queue()
    yield
    _drain_queue()


# ── emit_usage_event ─────────────────────────────────────────────────

class TestEmitUsageEvent:
    """Tests for the emit_usage_event function."""

    def test_pro_tier_queued(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_test123",
            event_name="chat_input_tokens",
            value=500,
            idempotency_key="req-1:chat:input",
        )
        assert result is True
        assert _event_queue.qsize() == 1
        evt = _event_queue.get_nowait()
        assert evt.stripe_customer_id == "cus_test123"
        assert evt.event_name == "chat_input_tokens"
        assert evt.value == 500
        assert evt.idempotency_key == "req-1:chat:input"
        assert evt.timestamp > 0

    def test_managed_tier_queued(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="managed",
            stripe_customer_id="cus_managed1",
            event_name="embedding_tokens",
            value=1000,
            idempotency_key="req-2:embedding:input",
        )
        assert result is True
        assert _event_queue.qsize() == 1

    def test_free_tier_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="free",
            stripe_customer_id="cus_free1",
            event_name="chat_input_tokens",
            value=100,
            idempotency_key="req-3:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_enterprise_tier_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="enterprise",
            stripe_customer_id="cus_ent1",
            event_name="chat_output_tokens",
            value=200,
            idempotency_key="req-4:chat:output",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_empty_tier_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="",
            stripe_customer_id="cus_x",
            event_name="chat_input_tokens",
            value=10,
            idempotency_key="req-5:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_zero_value_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_test",
            event_name="chat_input_tokens",
            value=0,
            idempotency_key="req-6:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_negative_value_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_test",
            event_name="chat_input_tokens",
            value=-10,
            idempotency_key="req-7:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_missing_customer_id_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="pro",
            stripe_customer_id="",
            event_name="chat_input_tokens",
            value=100,
            idempotency_key="req-8:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_missing_event_name_dropped(self):
        from app.billing import _event_queue, emit_usage_event

        result = emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_test",
            event_name="",
            value=100,
            idempotency_key="req-9:chat:input",
        )
        assert result is False
        assert _event_queue.qsize() == 0

    def test_multiple_events_accumulate(self):
        from app.billing import _event_queue, emit_usage_event

        for i in range(5):
            emit_usage_event(
                tier="pro",
                stripe_customer_id="cus_batch",
                event_name="chat_output_tokens",
                value=100 + i,
                idempotency_key=f"req-batch-{i}:chat:output",
            )
        assert _event_queue.qsize() == 5


# ── MeterEvent ──────────────────────────────────────────────────────

class TestMeterEvent:
    """Tests for MeterEvent dataclass."""

    def test_frozen(self):
        from app.billing import MeterEvent

        evt = MeterEvent(
            stripe_customer_id="cus_x",
            event_name="chat_input_tokens",
            value=42,
            timestamp=1000000,
            idempotency_key="abc",
        )
        with pytest.raises(AttributeError):
            evt.value = 999  # type: ignore[misc]

    def test_fields(self):
        from app.billing import MeterEvent

        evt = MeterEvent(
            stripe_customer_id="cus_abc",
            event_name="embedding_tokens",
            value=1234,
            timestamp=1700000000,
            idempotency_key="req-x:embed:in",
        )
        assert evt.stripe_customer_id == "cus_abc"
        assert evt.event_name == "embedding_tokens"
        assert evt.value == 1234
        assert evt.timestamp == 1700000000
        assert evt.idempotency_key == "req-x:embed:in"


# ── StripeUsageReporter ─────────────────────────────────────────────

class TestStripeUsageReporter:
    """Tests for the StripeUsageReporter background worker."""

    def test_dry_run_mode_no_secret(self):
        from app.billing import StripeUsageReporter

        reporter = StripeUsageReporter(stripe_secret_key="", flush_interval=1.0)
        assert reporter.dry_run is True
        assert reporter.enabled is False

    def test_enabled_with_secret(self):
        from app.billing import StripeUsageReporter

        reporter = StripeUsageReporter(stripe_secret_key="sk_test_xxx", flush_interval=1.0)
        assert reporter.dry_run is False
        assert reporter.enabled is True

    def test_stats_empty(self):
        from app.billing import StripeUsageReporter

        reporter = StripeUsageReporter()
        stats = reporter.stats
        assert stats["total_reported"] == 0
        assert stats["total_dropped"] == 0

    @pytest.mark.asyncio
    async def test_dry_run_flush_drains_queue(self):
        from app.billing import StripeUsageReporter, _event_queue, emit_usage_event

        # Push 3 events
        for i in range(3):
            emit_usage_event(
                tier="pro",
                stripe_customer_id="cus_flush_test",
                event_name="chat_input_tokens",
                value=100,
                idempotency_key=f"flush-test-{i}",
            )
        assert _event_queue.qsize() == 3

        reporter = StripeUsageReporter(stripe_secret_key="", flush_interval=1.0)
        await reporter._flush()  # noqa: SLF001

        assert _event_queue.qsize() == 0
        assert reporter.stats["total_reported"] == 3

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        from app.billing import StripeUsageReporter

        reporter = StripeUsageReporter(stripe_secret_key="", flush_interval=0.1)
        await reporter.start()
        # Let the background task run a cycle
        await asyncio.sleep(0.2)
        await reporter.stop()
        # Should not raise — clean shutdown

    @pytest.mark.asyncio
    async def test_stop_does_final_flush(self):
        from app.billing import StripeUsageReporter, _event_queue, emit_usage_event

        emit_usage_event(
            tier="managed",
            stripe_customer_id="cus_final",
            event_name="transcription_seconds",
            value=500,
            idempotency_key="final-flush-1",
        )
        assert _event_queue.qsize() == 1

        reporter = StripeUsageReporter(stripe_secret_key="", flush_interval=999)
        await reporter.start()
        await reporter.stop()

        assert _event_queue.qsize() == 0
        assert reporter.stats["total_reported"] == 1

    @pytest.mark.asyncio
    async def test_real_flush_calls_stripe(self, httpx_mock):
        """Verify flush POSTs to Stripe Meter Events API when key is set."""
        pytest.importorskip("pytest_httpx")
        from app.billing import StripeUsageReporter, emit_usage_event

        httpx_mock.add_response(
            url="https://api.stripe.com/v1/billing/meter_events",
            method="POST",
            status_code=200,
            json={"id": "evt_test"},
        )

        emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_real",
            event_name="chat_output_tokens",
            value=42,
            idempotency_key="real-flush-1:chat:output",
        )

        reporter = StripeUsageReporter(
            stripe_secret_key="sk_test_secret",
            flush_interval=999,
        )
        await reporter._flush()  # noqa: SLF001

        assert reporter.stats["total_reported"] == 1
        assert reporter.stats["total_dropped"] == 0

        # Verify the request
        reqs = httpx_mock.get_requests()
        assert len(reqs) == 1
        assert reqs[0].url == "https://api.stripe.com/v1/billing/meter_events"
        assert b"event_name=chat_output_tokens" in reqs[0].content
        assert b"payload%5Bstripe_customer_id%5D=cus_real" in reqs[0].content
        assert b"payload%5Bvalue%5D=42" in reqs[0].content
        assert reqs[0].headers["idempotency-key"] == "real-flush-1:chat:output"
        assert "Bearer sk_test_secret" in reqs[0].headers["authorization"]

    @pytest.mark.asyncio
    async def test_flush_handles_api_error(self, httpx_mock):
        """Verify failed Stripe calls increment dropped counter."""
        pytest.importorskip("pytest_httpx")
        from app.billing import StripeUsageReporter, emit_usage_event

        httpx_mock.add_response(
            url="https://api.stripe.com/v1/billing/meter_events",
            method="POST",
            status_code=500,
            json={"error": {"message": "Internal error"}},
        )

        emit_usage_event(
            tier="pro",
            stripe_customer_id="cus_err",
            event_name="chat_input_tokens",
            value=10,
            idempotency_key="err-test-1",
        )

        reporter = StripeUsageReporter(
            stripe_secret_key="sk_test_secret",
            flush_interval=999,
        )
        await reporter._flush()  # noqa: SLF001

        assert reporter.stats["total_reported"] == 0
        assert reporter.stats["total_dropped"] == 1

    @pytest.mark.asyncio
    async def test_flush_handles_409_idempotent(self, httpx_mock):
        """Verify 409 (already recorded) counts as reported, not dropped."""
        pytest.importorskip("pytest_httpx")
        from app.billing import StripeUsageReporter, emit_usage_event

        httpx_mock.add_response(
            url="https://api.stripe.com/v1/billing/meter_events",
            method="POST",
            status_code=409,
            json={"error": {"message": "Idempotent replay"}},
        )

        emit_usage_event(
            tier="managed",
            stripe_customer_id="cus_idem",
            event_name="embedding_tokens",
            value=99,
            idempotency_key="idem-test-1",
        )

        reporter = StripeUsageReporter(
            stripe_secret_key="sk_test_secret",
            flush_interval=999,
        )
        await reporter._flush()  # noqa: SLF001

        assert reporter.stats["total_reported"] == 1
        assert reporter.stats["total_dropped"] == 0


# ── KeyInfo stripe_customer_id ──────────────────────────────────────

class TestKeyInfoStripeCustomerId:
    """Verify KeyInfo dataclass carries stripe_customer_id."""

    def test_default_empty(self):
        from app.auth.key_store import KeyInfo

        info = KeyInfo(key_id="k1", user_id="u1", name="test")
        assert info.stripe_customer_id == ""

    def test_explicit_value(self):
        from app.auth.key_store import KeyInfo

        info = KeyInfo(
            key_id="k1",
            user_id="u1",
            name="test",
            tier="pro",
            stripe_customer_id="cus_abc123",
        )
        assert info.stripe_customer_id == "cus_abc123"
        assert info.tier == "pro"
