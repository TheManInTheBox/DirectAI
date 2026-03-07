"""
Fallback chain execution with circuit breaker.

When the primary model fails (5xx, 429, timeout), the executor
automatically retries with the next model in the fallback chain.
Client errors (4xx except 429) are NOT retried.

Each model has a circuit breaker that tracks recent success/failure rates.
Models with > 50% failure rate in the last 60 seconds are skipped
(circuit open). A half-open probe is attempted every 30 seconds.

Response headers:
  - X-Model-Used:       actual model that served the request
  - X-Fallback-From:    original model that failed (only on fallback)
  - X-Fallback-Reason:  why fallback was triggered (timeout/error/circuit_open)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from prometheus_client import Counter, Gauge

from app.metrics import REGISTRY

logger = logging.getLogger("directai.router")

# ── Prometheus metrics ──────────────────────────────────────────────

FALLBACK_TRIGGERED = Counter(
    "directai_fallback_triggered_total",
    "Total fallback activations.",
    ["primary_model", "fallback_model", "reason"],
    registry=REGISTRY,
)

FALLBACK_CHAIN_EXHAUSTED = Counter(
    "directai_fallback_chain_exhausted_total",
    "Total times all models in a fallback chain failed.",
    registry=REGISTRY,
)

MODEL_HEALTH_STATUS = Gauge(
    "directai_model_health_status",
    "Model health: 1=healthy, 0=unhealthy.",
    ["model"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_STATE = Gauge(
    "directai_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=open, 2=half-open.",
    ["model"],
    registry=REGISTRY,
)


# ── Circuit breaker ─────────────────────────────────────────────────


class CircuitState(Enum):
    CLOSED = 0       # Normal — requests flow through
    OPEN = 1         # Tripped — skip this model
    HALF_OPEN = 2    # Recovery probe — allow one request


@dataclass
class CircuitBreaker:
    """Per-model circuit breaker with rolling failure window."""

    model: str
    window_seconds: float = 60.0
    failure_threshold: float = 0.5     # Open at > 50% failure rate
    half_open_interval: float = 30.0   # Seconds between half-open probes
    min_requests: int = 3              # Minimum requests before evaluating

    # Internal state
    _successes: list[float] = field(default_factory=list)
    _failures: list[float] = field(default_factory=list)
    _state: CircuitState = CircuitState.CLOSED
    _last_failure_time: float = 0.0
    _last_half_open_attempt: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Evaluate current circuit state."""
        now = time.monotonic()
        self._prune_window(now)

        if self._state == CircuitState.OPEN:
            # Check if enough time has passed for a half-open probe
            if now - self._last_failure_time >= self.half_open_interval:
                self._state = CircuitState.HALF_OPEN
                CIRCUIT_BREAKER_STATE.labels(model=self.model).set(2)
            return self._state

        total = len(self._successes) + len(self._failures)
        if total >= self.min_requests:
            failure_rate = len(self._failures) / total
            if failure_rate > self.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_failure_time = now
                CIRCUIT_BREAKER_STATE.labels(model=self.model).set(1)
                MODEL_HEALTH_STATUS.labels(model=self.model).set(0)
                logger.warning(
                    "Circuit breaker OPEN for model '%s' (failure_rate=%.1f%%)",
                    self.model, failure_rate * 100,
                )
                return self._state

        return self._state

    def record_success(self) -> None:
        """Record a successful request."""
        now = time.monotonic()
        self._successes.append(now)

        if self._state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
            # Half-open probe succeeded — reset failure history so the
            # state property doesn't immediately re-trip on stale failures.
            self._failures.clear()
            self._state = CircuitState.CLOSED
            CIRCUIT_BREAKER_STATE.labels(model=self.model).set(0)
            MODEL_HEALTH_STATUS.labels(model=self.model).set(1)
            logger.info("Circuit breaker CLOSED for model '%s' (recovered)", self.model)

    def record_failure(self) -> None:
        """Record a failed request."""
        now = time.monotonic()
        self._failures.append(now)
        self._last_failure_time = now

        if self._state == CircuitState.HALF_OPEN:
            # Half-open probe failed — reopen
            self._state = CircuitState.OPEN
            CIRCUIT_BREAKER_STATE.labels(model=self.model).set(1)
            logger.warning("Circuit breaker re-OPENED for model '%s' (half-open probe failed)", self.model)

    def should_allow(self) -> bool:
        """Returns True if a request should be allowed through."""
        state = self.state  # triggers evaluation
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            now = time.monotonic()
            if now - self._last_half_open_attempt >= self.half_open_interval:
                self._last_half_open_attempt = now
                return True  # Allow one probe
            return False
        return False  # OPEN

    def _prune_window(self, now: float) -> None:
        """Remove entries older than the rolling window."""
        cutoff = now - self.window_seconds
        self._successes = [t for t in self._successes if t > cutoff]
        self._failures = [t for t in self._failures if t > cutoff]


# ── Fallback executor ──────────────────────────────────────────────

# HTTP status codes that trigger fallback
_FALLBACK_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Status codes that should NOT trigger fallback (client errors)
_NO_RETRY_STATUS_CODES = frozenset({400, 401, 403, 404, 405, 409, 413, 422})


class AllModelsFailedError(Exception):
    """Raised when all models in a fallback chain have failed."""

    def __init__(self, chain: list[str], errors: list[str]) -> None:
        self.chain = chain
        self.errors = errors
        super().__init__(f"All {len(chain)} models in fallback chain failed: {errors}")


@dataclass
class FallbackResult:
    """Result of a fallback chain execution."""

    model_used: str
    response: object  # httpx.Response or similar
    fallback_from: Optional[str] = None
    fallback_reason: Optional[str] = None
    attempts: int = 1


class FallbackExecutor:
    """
    Executes a fallback chain with circuit-breaker protection.

    Usage::

        executor = FallbackExecutor()
        result = await executor.execute(
            chain=["model-a", "model-b", "model-c"],
            execute_fn=async_proxy_function,
        )
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_breaker(self, model: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a model."""
        if model not in self._breakers:
            self._breakers[model] = CircuitBreaker(model=model)
        return self._breakers[model]

    async def execute(
        self,
        chain: list[str],
        execute_fn,
        *,
        timeout_seconds: float = 30.0,
    ) -> FallbackResult:
        """
        Execute requests through the fallback chain until one succeeds.

        ``execute_fn(model_name: str) -> response`` is called for each model.
        The response must have a ``status_code`` attribute.

        Raises ``AllModelsFailedError`` if all models in the chain fail.
        """
        if not chain:
            raise ValueError("Fallback chain is empty")

        primary = chain[0]
        errors: list[str] = []

        for i, model_name in enumerate(chain):
            breaker = self.get_breaker(model_name)

            # Circuit breaker check
            if not breaker.should_allow():
                reason = "circuit_open"
                errors.append(f"{model_name}: circuit open")
                logger.info("Skipping model '%s' (circuit open)", model_name)
                if i > 0 or len(chain) > 1:
                    FALLBACK_TRIGGERED.labels(
                        primary_model=primary,
                        fallback_model=model_name,
                        reason=reason,
                    ).inc()
                continue

            try:
                response = await execute_fn(model_name)

                # Check if response triggers fallback
                if hasattr(response, "status_code"):
                    status = response.status_code

                    if status in _NO_RETRY_STATUS_CODES:
                        # Client error — return immediately, don't fallback
                        breaker.record_success()
                        return FallbackResult(
                            model_used=model_name,
                            response=response,
                            fallback_from=primary if i > 0 else None,
                            attempts=i + 1,
                        )

                    if status in _FALLBACK_STATUS_CODES:
                        # Server error — try next model
                        breaker.record_failure()
                        reason = f"http_{status}"
                        errors.append(f"{model_name}: HTTP {status}")
                        logger.warning(
                            "Model '%s' returned %d — falling back", model_name, status
                        )
                        FALLBACK_TRIGGERED.labels(
                            primary_model=primary,
                            fallback_model=model_name,
                            reason=reason,
                        ).inc()
                        continue

                # Success
                breaker.record_success()
                return FallbackResult(
                    model_used=model_name,
                    response=response,
                    fallback_from=primary if i > 0 else None,
                    fallback_reason=errors[-1] if i > 0 and errors else None,
                    attempts=i + 1,
                )

            except Exception as exc:
                breaker.record_failure()
                reason = "timeout" if "timeout" in str(exc).lower() else "error"
                errors.append(f"{model_name}: {type(exc).__name__}: {exc}")
                logger.warning("Model '%s' failed: %s — falling back", model_name, exc)
                FALLBACK_TRIGGERED.labels(
                    primary_model=primary,
                    fallback_model=model_name,
                    reason=reason,
                ).inc()
                continue

        # All models failed
        FALLBACK_CHAIN_EXHAUSTED.inc()
        raise AllModelsFailedError(chain, errors)
