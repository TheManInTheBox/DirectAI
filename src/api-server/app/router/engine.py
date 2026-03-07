"""
Core routing engine — evaluates route configs and selects target model.

The engine is backward-compatible: if no custom routes exist for a
request, it falls back to the existing ``ModelRegistry.resolve()``
alias-based resolution. Custom routes override alias resolution when
they match.

Strategies:
  - direct:     Always route to a specific model
  - complexity: Route based on input token count / message count
  - cost:       Route to cheapest model meeting quality threshold
  - latency:    Route to fastest model (from recent metrics)
  - random:     Weighted random selection (A/B testing)
  - fallback:   Return first model in chain + remaining as fallback
"""

from __future__ import annotations

import fnmatch
import logging
import random
import re
import time
from typing import Optional

from prometheus_client import Counter, Histogram

from app.metrics import REGISTRY
from app.router.schemas import (
    InferenceContext,
    RouteConfig,
    RoutingDecision,
    RoutingRule,
    RoutingStrategy,
)

logger = logging.getLogger("directai.router")

# ── Prometheus metrics ──────────────────────────────────────────────

ROUTING_DECISIONS = Counter(
    "directai_routing_decisions_total",
    "Total routing decisions made.",
    ["strategy", "target_model"],
    registry=REGISTRY,
)

ROUTING_DURATION = Histogram(
    "directai_routing_duration_seconds",
    "Time spent evaluating routing rules.",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01),
    registry=REGISTRY,
)

ROUTING_FALLBACK_TRIGGERED = Counter(
    "directai_routing_fallback_triggered_total",
    "Total fallback activations during routing evaluation.",
    registry=REGISTRY,
)


class RoutingEngine:
    """
    Evaluates route configurations and returns a ``RoutingDecision``.

    Usage::

        engine = RoutingEngine(route_repo, model_registry)
        decision = engine.resolve(context)
        # decision.model = target model name
        # decision.fallback_chain = remaining fallback models
    """

    def __init__(self, route_repo, model_registry=None) -> None:
        self._repo = route_repo
        self._registry = model_registry

    def resolve(self, ctx: InferenceContext) -> RoutingDecision:
        """
        Evaluate all matching routes and return a routing decision.

        Falls back to direct model resolution if no custom routes match.
        """
        start = time.monotonic()
        try:
            return self._resolve_inner(ctx)
        finally:
            elapsed = time.monotonic() - start
            ROUTING_DURATION.observe(elapsed)

    def _resolve_inner(self, ctx: InferenceContext) -> RoutingDecision:
        routes = self._get_matching_routes(ctx)

        if not routes:
            # No custom routes — fall back to direct alias resolution
            return RoutingDecision(
                model=ctx.model_requested,
                strategy="direct",
            )

        # Evaluate highest-priority matching route
        route = routes[0]
        decision = self._evaluate_route(route, ctx)

        ROUTING_DECISIONS.labels(
            strategy=decision.strategy,
            target_model=decision.model,
        ).inc()

        return decision

    def _get_matching_routes(self, ctx: InferenceContext) -> list[RouteConfig]:
        """Find all enabled routes that match the request context."""
        candidates = self._repo.get_routes_for_customer(ctx.customer_id)
        matched = []

        for route in candidates:
            if not route.enabled:
                continue
            if not self._matches(route, ctx):
                continue
            matched.append(route)

        return matched

    @staticmethod
    def _matches(route: RouteConfig, ctx: InferenceContext) -> bool:
        """Check if a route's match conditions apply to this request."""
        m = route.match

        # Endpoint match
        if m.endpoint != "*" and m.endpoint != ctx.endpoint:
            return False

        # Model match (glob patterns)
        if m.models != ["*"]:
            if not any(
                fnmatch.fnmatch(ctx.model_requested, pattern)
                for pattern in m.models
            ):
                return False

        # Header match (all required headers must be present)
        for key, value in m.headers.items():
            if ctx.headers.get(key) != value:
                return False

        return True

    def _evaluate_route(
        self, route: RouteConfig, ctx: InferenceContext
    ) -> RoutingDecision:
        """Apply the route's strategy to produce a routing decision."""
        strategy = route.strategy

        if strategy == RoutingStrategy.DIRECT:
            return self._eval_direct(route, ctx)
        elif strategy == RoutingStrategy.COMPLEXITY:
            return self._eval_complexity(route, ctx)
        elif strategy == RoutingStrategy.COST:
            return self._eval_cost(route, ctx)
        elif strategy == RoutingStrategy.LATENCY:
            return self._eval_latency(route, ctx)
        elif strategy == RoutingStrategy.RANDOM:
            return self._eval_random(route, ctx)
        elif strategy == RoutingStrategy.FALLBACK:
            return self._eval_fallback(route, ctx)
        else:
            logger.warning("Unknown strategy '%s' on route %s — using direct", strategy, route.route_id)
            return self._eval_direct(route, ctx)

    def _eval_direct(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """Direct routing: use the first rule's target or the requested model."""
        target = route.rules[0].target if route.rules else ctx.model_requested
        return RoutingDecision(
            model=target,
            route_id=route.route_id,
            strategy="direct",
            fallback_chain=route.fallback_chain,
        )

    def _eval_complexity(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """
        Complexity-based routing: evaluate rules against token count and
        message count. First matching rule wins.
        """
        for rule in route.rules:
            if _evaluate_condition(rule.condition, ctx):
                return RoutingDecision(
                    model=rule.target,
                    route_id=route.route_id,
                    strategy="complexity",
                    fallback_chain=route.fallback_chain,
                )

        # No rule matched — use requested model
        return RoutingDecision(
            model=ctx.model_requested,
            route_id=route.route_id,
            strategy="complexity",
            fallback_chain=route.fallback_chain,
        )

    def _eval_cost(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """Cost-based routing: pick cheapest model from rules (lowest weight = cheapest)."""
        # Sort rules by weight ascending (lower weight = cheaper)
        sorted_rules = sorted(route.rules, key=lambda r: r.weight)
        for rule in sorted_rules:
            if _evaluate_condition(rule.condition, ctx):
                return RoutingDecision(
                    model=rule.target,
                    route_id=route.route_id,
                    strategy="cost",
                    fallback_chain=route.fallback_chain,
                )

        return RoutingDecision(
            model=ctx.model_requested,
            route_id=route.route_id,
            strategy="cost",
            fallback_chain=route.fallback_chain,
        )

    def _eval_latency(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """Latency-based routing: for now, pick first healthy model from rules."""
        # TODO: Wire to real latency metrics from Prometheus
        for rule in route.rules:
            if _evaluate_condition(rule.condition, ctx):
                return RoutingDecision(
                    model=rule.target,
                    route_id=route.route_id,
                    strategy="latency",
                    fallback_chain=route.fallback_chain,
                )

        return RoutingDecision(
            model=ctx.model_requested,
            route_id=route.route_id,
            strategy="latency",
            fallback_chain=route.fallback_chain,
        )

    def _eval_random(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """Weighted random selection across rules."""
        if not route.rules:
            return RoutingDecision(
                model=ctx.model_requested,
                route_id=route.route_id,
                strategy="random",
            )

        targets = [r.target for r in route.rules]
        weights = [r.weight for r in route.rules]

        chosen = random.choices(targets, weights=weights, k=1)[0]

        # Determine A/B variant name
        ab_variant = None
        if route.ab_test:
            for variant in route.ab_test.variants:
                if variant.model == chosen:
                    ab_variant = variant.name
                    break

        return RoutingDecision(
            model=chosen,
            route_id=route.route_id,
            strategy="random",
            ab_variant=ab_variant,
            fallback_chain=route.fallback_chain,
        )

    def _eval_fallback(self, route: RouteConfig, ctx: InferenceContext) -> RoutingDecision:
        """Fallback strategy: use first model in chain, rest as fallback."""
        chain = route.fallback_chain or [ctx.model_requested]
        primary = chain[0]
        remaining = chain[1:] if len(chain) > 1 else []

        return RoutingDecision(
            model=primary,
            route_id=route.route_id,
            strategy="fallback",
            fallback_chain=remaining,
        )


# ── Condition evaluator ─────────────────────────────────────────────

# Simple safe expression evaluator for conditions like:
#   "token_count < 100"
#   "token_count >= 100"
#   "message_count == 1"
#   "true"

_CONDITION_RE = re.compile(
    r"^(token_count|message_count)\s*(==|!=|<|<=|>|>=)\s*(\d+)$"
)


def _evaluate_condition(condition: str, ctx: InferenceContext) -> bool:
    """
    Safely evaluate a routing condition against request context.

    Only supports simple comparisons on ``token_count`` and ``message_count``.
    Returns True for unrecognized conditions (fail-open).
    """
    condition = condition.strip()

    if condition.lower() in ("true", "always", "*"):
        return True
    if condition.lower() in ("false", "never"):
        return False

    match = _CONDITION_RE.match(condition)
    if not match:
        logger.warning("Unrecognized routing condition: '%s' — treating as true", condition)
        return True

    var_name, op, threshold_str = match.groups()
    threshold = int(threshold_str)

    if var_name == "token_count":
        value = ctx.token_count_estimate
    elif var_name == "message_count":
        value = ctx.message_count
    else:
        return True

    if op == "==":
        return value == threshold
    elif op == "!=":
        return value != threshold
    elif op == "<":
        return value < threshold
    elif op == "<=":
        return value <= threshold
    elif op == ">":
        return value > threshold
    elif op == ">=":
        return value >= threshold

    return True
