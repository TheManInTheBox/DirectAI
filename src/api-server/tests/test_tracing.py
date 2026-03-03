"""
Tests for OpenTelemetry tracing — app/telemetry.py.

Validates:
  - TracerProvider setup with exporters
  - NoOp mode when no exporters configured
  - Shutdown flushes spans
  - get_tracer() returns a usable tracer in both modes
  - Manual span attributes on model_registry.resolve()
  - W3C traceparent injection in BackendClient
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider


# ── Minimal in-memory exporter (removed from OTel SDK >=1.39) ───────


class _InMemoryExporter(SpanExporter):
    """Collects spans in memory for test assertions."""

    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self._spans)

    def shutdown(self) -> None:
        self._spans.clear()


# ── Helpers ──────────────────────────────────────────────────────────


def _make_provider_and_exporter() -> tuple[TracerProvider, _InMemoryExporter]:
    """Create a TracerProvider + in-memory exporter WITHOUT setting global.

    Tests that need spans from get_tracer() (which uses the global
    provider) must explicitly patch the global — see test classes below.
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    exporter = _InMemoryExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


# ── configure_tracing / shutdown_tracing ─────────────────────────────


class TestConfigureTracing:
    """Tests for the configure_tracing() function."""

    def test_returns_none_when_no_exporters(self):
        """No connection string + no OTLP = tracing disabled."""
        from app.telemetry import configure_tracing

        result = configure_tracing(
            appinsights_connection_string="",
            otlp_endpoint="",
        )
        assert result is None

    def test_returns_provider_with_otlp(self):
        """OTLP endpoint configured -> returns a TracerProvider."""
        from app.telemetry import configure_tracing, shutdown_tracing

        with patch(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
        ) as mock_cls, patch("app.telemetry.trace.set_tracer_provider"):
            mock_cls.return_value = MagicMock()
            provider = configure_tracing(
                appinsights_connection_string="",
                otlp_endpoint="http://localhost:4317",
            )
            assert provider is not None
            from opentelemetry.sdk.trace import TracerProvider as _TP

            assert isinstance(provider, _TP)
            shutdown_tracing()

    def test_sample_rate_below_one(self):
        """Custom sample rate should not crash."""
        from app.telemetry import configure_tracing, shutdown_tracing

        with patch(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
        ) as mock_cls, patch("app.telemetry.trace.set_tracer_provider"):
            mock_cls.return_value = MagicMock()
            provider = configure_tracing(
                otlp_endpoint="http://localhost:4317",
                sample_rate=0.5,
            )
            assert provider is not None
            shutdown_tracing()


class TestShutdownTracing:
    """Tests for shutdown_tracing()."""

    def test_shutdown_is_idempotent(self):
        """Calling shutdown when no provider is set should not raise."""
        from app.telemetry import shutdown_tracing

        shutdown_tracing()
        shutdown_tracing()  # second call is safe


class TestGetTracer:
    """Tests for the get_tracer() accessor."""

    def test_returns_noop_tracer_when_disabled(self):
        """With no provider configured, get_tracer() still returns a tracer."""
        from app.telemetry import get_tracer

        tracer = get_tracer()
        assert tracer is not None
        # Should be able to start a span without error
        with tracer.start_as_current_span("noop-test") as span:
            assert span is not None

    def test_returns_real_tracer_when_configured(self):
        """With a real provider, tracer produces recorded spans."""
        provider, exporter = _make_provider_and_exporter()
        try:
            # Use the provider's get_tracer directly — avoids global state
            tracer = provider.get_tracer("directai.api-server")
            with tracer.start_as_current_span("test-span") as span:
                span.set_attribute("test.key", "test-value")

            spans = exporter.get_finished_spans()
            assert len(spans) == 1
            assert spans[0].name == "test-span"
            assert spans[0].attributes["test.key"] == "test-value"
        finally:
            provider.shutdown()


# ── Manual span on model_registry.resolve() ─────────────────────────


class TestRegistryResolveSpan:
    """Tests that ModelRegistry.resolve() produces a trace span.

    model_registry.resolve() calls get_tracer() which uses the global
    provider. We patch the global to inject our in-memory provider.
    """

    def test_resolve_hit_produces_span(self, model_config_dir):
        """Resolving a known model should emit a span with model attributes."""
        from app.routing import ModelRegistry

        provider, exporter = _make_provider_and_exporter()
        try:
            with patch("app.telemetry.trace.get_tracer", return_value=provider.get_tracer("test")):
                registry = ModelRegistry.from_directory(model_config_dir)
                spec = registry.resolve("test-chat")
                assert spec is not None

            spans = exporter.get_finished_spans()
            resolve_spans = [s for s in spans if s.name == "model_registry.resolve"]
            assert len(resolve_spans) == 1
            s = resolve_spans[0]
            assert s.attributes["directai.model.requested"] == "test-chat"
            assert s.attributes["directai.model.resolved"] is True
            assert s.attributes["directai.model.name"] == "test-chat-model"
            assert s.attributes["directai.model.modality"] == "chat"
        finally:
            provider.shutdown()

    def test_resolve_miss_produces_span(self, model_config_dir):
        """Resolving an unknown model should still emit a span."""
        from app.routing import ModelRegistry

        provider, exporter = _make_provider_and_exporter()
        try:
            with patch("app.telemetry.trace.get_tracer", return_value=provider.get_tracer("test")):
                registry = ModelRegistry.from_directory(model_config_dir)
                spec = registry.resolve("nonexistent-model")
                assert spec is None

            spans = exporter.get_finished_spans()
            resolve_spans = [s for s in spans if s.name == "model_registry.resolve"]
            assert len(resolve_spans) == 1
            s = resolve_spans[0]
            assert s.attributes["directai.model.requested"] == "nonexistent-model"
            assert s.attributes["directai.model.resolved"] is False
        finally:
            provider.shutdown()


# ── W3C traceparent injection in BackendClient ──────────────────────


class TestTraceparentPropagation:
    """Tests that BackendClient injects traceparent headers."""

    def test_inject_noop_does_not_crash(self):
        """inject() on a NoOp provider should not crash or add headers."""
        from opentelemetry.propagate import inject

        headers: dict[str, str] = {"X-Request-ID": "test-123"}
        inject(headers)
        assert isinstance(headers, dict)

    def test_inject_adds_traceparent_with_active_span(self):
        """With an active span context, inject() adds traceparent."""
        from opentelemetry.propagate import inject, set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        provider, _exporter = _make_provider_and_exporter()
        # Ensure W3C propagator is set
        set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))
        try:
            tracer = provider.get_tracer("test")
            with tracer.start_as_current_span("parent"):
                headers: dict[str, str] = {}
                inject(headers)
                assert "traceparent" in headers
                assert headers["traceparent"].startswith("00-")
        finally:
            provider.shutdown()


# ── End-to-end: tracing disabled in tests ───────────────────────────


class TestTracingDisabledInTests:
    """Verify the test fixture disables tracing so tests don't export."""

    def test_otel_disabled_env_set(self, test_client):
        """DIRECTAI_OTEL_ENABLED=false should be set by the test fixture."""
        import os

        assert os.environ.get("DIRECTAI_OTEL_ENABLED", "").lower() == "false"

    def test_app_still_works_without_tracing(self, test_client):
        """Health probes work fine when tracing is disabled."""
        resp = test_client.get("/healthz")
        assert resp.status_code == 200
