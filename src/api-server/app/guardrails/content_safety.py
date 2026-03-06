"""
Azure AI Content Safety client wrapper.

Calls ``POST {endpoint}/contentsafety/text:analyze`` to classify text
across four severity categories: Hate, SelfHarm, Sexual, Violence.

When no endpoint is configured (``endpoint`` is empty), the client runs
in **stub mode** — every check returns severity 0 across all categories.
This lets the middleware run in dev/test without an Azure resource.

Prometheus metrics:
  - ``directai_content_safety_checks_total``   — counter by result (pass/block)
  - ``directai_content_safety_latency_seconds`` — histogram of API call duration
  - ``directai_content_safety_blocked_total``  — counter of blocked requests
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from prometheus_client import Counter, Histogram

from app.guardrails.config import GuardrailsConfig
from app.guardrails.schemas import CategoryResult, SafetyCategory, SafetyCheckResult
from app.metrics import REGISTRY

logger = logging.getLogger("directai.guardrails")

# ── Prometheus metrics ──────────────────────────────────────────────

SAFETY_CHECKS_TOTAL = Counter(
    "directai_content_safety_checks_total",
    "Total content safety checks performed.",
    ["result"],  # pass | block | error | bypass | stub
    registry=REGISTRY,
)

SAFETY_LATENCY = Histogram(
    "directai_content_safety_latency_seconds",
    "Latency of Azure AI Content Safety API calls.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

SAFETY_BLOCKED_TOTAL = Counter(
    "directai_content_safety_blocked_total",
    "Total requests blocked by content safety filters.",
    ["category"],
    registry=REGISTRY,
)


class ContentSafetyClient:
    """
    Async client for Azure AI Content Safety text analysis.

    Usage::

        client = ContentSafetyClient(config)
        await client.startup()
        result = await client.analyze("some text to check")
        await client.shutdown()

    In stub mode (no endpoint configured), ``analyze()`` always returns
    a passing result with severity 0 across all categories. Metrics
    are labelled ``stub`` instead of ``pass``.
    """

    def __init__(self, config: GuardrailsConfig) -> None:
        self._config = config
        self._http: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        """Create the HTTP client pool."""
        if self._config.is_live:
            self._http = httpx.AsyncClient(
                base_url=self._config.endpoint.rstrip("/"),
                headers={
                    "Ocp-Apim-Subscription-Key": self._config.api_key,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._config.timeout, connect=2.0),
            )
            logger.info(
                "Content Safety client initialized (endpoint=%s, threshold=%d)",
                self._config.endpoint,
                self._config.threshold,
            )
        else:
            logger.info("Content Safety client running in STUB mode (no endpoint configured)")

    async def shutdown(self) -> None:
        """Close the HTTP client pool."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def analyze(self, text: str) -> SafetyCheckResult:
        """
        Run content safety analysis on the given text.

        Returns a ``SafetyCheckResult`` with per-category severities.
        If the endpoint is not configured, returns a stub result.
        If the API call fails, returns a passing result (fail-open)
        and logs the error.
        """
        if not self._config.is_live or self._http is None:
            return self._stub_result()

        return await self._call_api(text)

    def _stub_result(self) -> SafetyCheckResult:
        """Return a passing stub result — all categories severity 0."""
        SAFETY_CHECKS_TOTAL.labels(result="stub").inc()
        return SafetyCheckResult(
            categories={
                cat.value: CategoryResult(severity=0, filtered=False)
                for cat in SafetyCategory
            },
            blocked=False,
            latency_ms=0.0,
        )

    async def _call_api(self, text: str) -> SafetyCheckResult:
        """Call Azure AI Content Safety text:analyze endpoint."""
        assert self._http is not None

        # Truncate very long text to avoid API limits (max 10K chars)
        truncated = text[:10_000] if len(text) > 10_000 else text

        payload = {
            "text": truncated,
            "categories": [cat.value for cat in SafetyCategory],
            "outputType": "FourSeverityLevels",
        }

        start = time.monotonic()
        try:
            resp = await self._http.post(
                f"/contentsafety/text:analyze?api-version={self._config.api_version}",
                json=payload,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            SAFETY_LATENCY.observe(elapsed_ms / 1000)

            if resp.status_code != 200:
                logger.error(
                    "Content Safety API returned %d: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                SAFETY_CHECKS_TOTAL.labels(result="error").inc()
                # Fail open — don't block users because the safety API is down
                return SafetyCheckResult(
                    categories={},
                    blocked=False,
                    latency_ms=elapsed_ms,
                )

            return self._parse_response(resp.json(), elapsed_ms)

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            SAFETY_LATENCY.observe(elapsed_ms / 1000)
            logger.error("Content Safety API call failed: %s", exc)
            SAFETY_CHECKS_TOTAL.labels(result="error").inc()
            # Fail open
            return SafetyCheckResult(
                categories={},
                blocked=False,
                latency_ms=elapsed_ms,
            )

    def _parse_response(self, data: dict, elapsed_ms: float) -> SafetyCheckResult:
        """Parse Content Safety API response and apply thresholds."""
        categories: dict[str, CategoryResult] = {}
        blocked = False

        for item in data.get("categoriesAnalysis", []):
            name = item.get("category", "Unknown")
            severity = item.get("severity", 0)

            # Per-category or default threshold
            threshold = self._config.category_thresholds.get(
                name, self._config.threshold
            )
            filtered = severity >= threshold

            categories[name] = CategoryResult(severity=severity, filtered=filtered)

            if filtered:
                blocked = True
                SAFETY_BLOCKED_TOTAL.labels(category=name).inc()

        result_label = "block" if blocked else "pass"
        SAFETY_CHECKS_TOTAL.labels(result=result_label).inc()

        return SafetyCheckResult(
            categories=categories,
            blocked=blocked,
            latency_ms=elapsed_ms,
        )
