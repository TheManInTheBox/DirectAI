"""
Tests for the model router module — schemas, repository, engine, fallback.

Covers:
  - RouteConfig schema creation and validation
  - RouteRepository CRUD (create, get, list, update, delete)
  - RouteRepository in-memory cache refresh
  - RoutingEngine strategy evaluation (direct, complexity, fallback, random)
  - RoutingEngine backward compatibility (no routes = direct resolution)
  - Condition evaluator (token_count, message_count comparisons)
  - CircuitBreaker state transitions (closed → open → half-open → closed)
  - FallbackExecutor chain execution (success, fallback, exhausted)
  - FallbackExecutor circuit breaker integration
  - API endpoints CRUD + evaluate
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.router.engine import RoutingEngine, _evaluate_condition
from app.router.fallback import (
    AllModelsFailedError,
    CircuitBreaker,
    CircuitState,
    FallbackExecutor,
    FallbackResult,
)
from app.router.repository import RouteRepository
from app.router.schemas import (
    InferenceContext,
    MatchConfig,
    RouteConfig,
    RouteCreate,
    RouteUpdate,
    RoutingDecision,
    RoutingRule,
    RoutingStrategy,
)


# ════════════════════════════════════════════════════════════════════
# Schema unit tests
# ════════════════════════════════════════════════════════════════════


class TestSchemas:
    def test_route_config_defaults(self):
        config = RouteConfig(name="test")
        assert config.strategy == RoutingStrategy.DIRECT
        assert config.enabled is True
        assert config.priority == 0
        assert config.match.endpoint == "/v1/chat/completions"

    def test_match_config_wildcard(self):
        m = MatchConfig(models=["*"])
        assert m.models == ["*"]

    def test_routing_rule(self):
        rule = RoutingRule(condition="token_count < 100", target="small-model")
        assert rule.weight == 100

    def test_routing_decision(self):
        d = RoutingDecision(model="test-model", strategy="complexity")
        assert d.fallback_chain == []
        assert d.ab_variant is None

    def test_inference_context(self):
        ctx = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="gpt-4",
            token_count_estimate=50,
            message_count=2,
        )
        assert ctx.customer_id == "default"


# ════════════════════════════════════════════════════════════════════
# Condition evaluator unit tests
# ════════════════════════════════════════════════════════════════════


class TestConditionEvaluator:
    def _ctx(self, tokens: int = 0, messages: int = 0) -> InferenceContext:
        return InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="test",
            token_count_estimate=tokens,
            message_count=messages,
        )

    def test_true_literal(self):
        assert _evaluate_condition("true", self._ctx()) is True
        assert _evaluate_condition("always", self._ctx()) is True
        assert _evaluate_condition("*", self._ctx()) is True

    def test_false_literal(self):
        assert _evaluate_condition("false", self._ctx()) is False
        assert _evaluate_condition("never", self._ctx()) is False

    def test_token_count_less_than(self):
        assert _evaluate_condition("token_count < 100", self._ctx(tokens=50)) is True
        assert _evaluate_condition("token_count < 100", self._ctx(tokens=100)) is False
        assert _evaluate_condition("token_count < 100", self._ctx(tokens=150)) is False

    def test_token_count_gte(self):
        assert _evaluate_condition("token_count >= 100", self._ctx(tokens=100)) is True
        assert _evaluate_condition("token_count >= 100", self._ctx(tokens=99)) is False

    def test_message_count(self):
        assert _evaluate_condition("message_count == 1", self._ctx(messages=1)) is True
        assert _evaluate_condition("message_count == 1", self._ctx(messages=3)) is False

    def test_unrecognized_condition_returns_true(self):
        """Unrecognized conditions fail-open (return True)."""
        assert _evaluate_condition("unknown_var > 5", self._ctx()) is True


# ════════════════════════════════════════════════════════════════════
# RouteRepository unit tests
# ════════════════════════════════════════════════════════════════════


class TestRouteRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        created = await repo.create(RouteCreate(
            name="test-route",
            strategy=RoutingStrategy.COMPLEXITY,
            rules=[
                RoutingRule(condition="token_count < 100", target="small-model"),
                RoutingRule(condition="token_count >= 100", target="large-model"),
            ],
            fallback_chain=["small-model", "large-model"],
        ))

        assert created.name == "test-route"
        assert created.strategy == RoutingStrategy.COMPLEXITY
        assert len(created.rules) == 2

        fetched = await repo.get(created.route_id)
        assert fetched is not None
        assert fetched.name == "test-route"

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_list_routes(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(name="route-a", priority=10))
        await repo.create(RouteCreate(name="route-b", priority=20))

        routes = await repo.list_routes()
        assert len(routes) == 2
        assert routes[0].name == "route-b"  # Higher priority first

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_update(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        created = await repo.create(RouteCreate(name="original"))
        updated = await repo.update(
            created.route_id,
            RouteUpdate(name="renamed", priority=50),
        )

        assert updated is not None
        assert updated.name == "renamed"
        assert updated.priority == 50

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_delete(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        created = await repo.create(RouteCreate(name="to-delete"))
        assert await repo.delete(created.route_id) is True
        assert await repo.get(created.route_id) is None
        assert await repo.delete("nonexistent") is False

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_cache_by_customer(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(name="cust-a", customer_id="a"))
        await repo.create(RouteCreate(name="cust-b", customer_id="b"))

        assert len(repo.get_routes_for_customer("a")) == 1
        assert len(repo.get_routes_for_customer("b")) == 1
        assert len(repo.get_routes_for_customer("c")) == 0

        await repo.shutdown()


# ════════════════════════════════════════════════════════════════════
# RoutingEngine unit tests
# ════════════════════════════════════════════════════════════════════


class TestRoutingEngine:
    @pytest.mark.asyncio
    async def test_no_routes_returns_direct(self):
        """No custom routes → fall back to direct alias resolution."""
        repo = RouteRepository(":memory:")
        await repo.startup()
        engine = RoutingEngine(repo)

        ctx = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="qwen2.5-3b",
        )
        decision = engine.resolve(ctx)
        assert decision.model == "qwen2.5-3b"
        assert decision.strategy == "direct"

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_complexity_routing(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(
            name="complexity-route",
            strategy=RoutingStrategy.COMPLEXITY,
            match=MatchConfig(endpoint="/v1/chat/completions"),
            rules=[
                RoutingRule(condition="token_count < 100", target="small-model"),
                RoutingRule(condition="token_count >= 100", target="large-model"),
            ],
            priority=10,
        ))

        engine = RoutingEngine(repo)

        # Short query → small model
        ctx = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="any",
            token_count_estimate=50,
        )
        decision = engine.resolve(ctx)
        assert decision.model == "small-model"
        assert decision.strategy == "complexity"

        # Long query → large model
        ctx2 = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="any",
            token_count_estimate=500,
        )
        decision2 = engine.resolve(ctx2)
        assert decision2.model == "large-model"

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_fallback_strategy(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(
            name="fallback-route",
            strategy=RoutingStrategy.FALLBACK,
            fallback_chain=["model-a", "model-b", "model-c"],
            priority=10,
        ))

        engine = RoutingEngine(repo)
        ctx = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="any",
        )
        decision = engine.resolve(ctx)
        assert decision.model == "model-a"
        assert decision.fallback_chain == ["model-b", "model-c"]

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_endpoint_mismatch_skips_route(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(
            name="chat-only",
            match=MatchConfig(endpoint="/v1/chat/completions"),
            rules=[RoutingRule(condition="true", target="chat-model")],
            priority=10,
        ))

        engine = RoutingEngine(repo)

        # Embeddings endpoint → no match → direct resolution
        ctx = InferenceContext(
            endpoint="/v1/embeddings",
            model_requested="embed-model",
        )
        decision = engine.resolve(ctx)
        assert decision.model == "embed-model"
        assert decision.strategy == "direct"

        await repo.shutdown()

    @pytest.mark.asyncio
    async def test_random_strategy_picks_from_rules(self):
        repo = RouteRepository(":memory:")
        await repo.startup()

        await repo.create(RouteCreate(
            name="ab-test",
            strategy=RoutingStrategy.RANDOM,
            rules=[
                RoutingRule(condition="true", target="model-a", weight=50),
                RoutingRule(condition="true", target="model-b", weight=50),
            ],
            priority=10,
        ))

        engine = RoutingEngine(repo)
        ctx = InferenceContext(
            endpoint="/v1/chat/completions",
            model_requested="any",
        )

        # Run many times — should produce both models
        models_seen = set()
        for _ in range(100):
            d = engine.resolve(ctx)
            models_seen.add(d.model)

        assert "model-a" in models_seen
        assert "model-b" in models_seen

        await repo.shutdown()


# ════════════════════════════════════════════════════════════════════
# CircuitBreaker unit tests
# ════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(model="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.should_allow() is True

    def test_opens_on_failures(self):
        cb = CircuitBreaker(model="test", min_requests=3, failure_threshold=0.5)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.should_allow() is False

    def test_closes_on_success_after_half_open(self):
        cb = CircuitBreaker(
            model="test",
            min_requests=2,
            failure_threshold=0.5,
            half_open_interval=0.0,  # Immediate half-open for testing
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Force immediate transition to half-open
        cb._last_failure_time = time.monotonic() - 1.0
        assert cb.state == CircuitState.HALF_OPEN

        # Record success → closes circuit
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ════════════════════════════════════════════════════════════════════
# FallbackExecutor unit tests
# ════════════════════════════════════════════════════════════════════


class TestFallbackExecutor:
    @pytest.mark.asyncio
    async def test_success_on_first_model(self):
        executor = FallbackExecutor()

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def execute_fn(model: str):
            return mock_response

        result = await executor.execute(["model-a", "model-b"], execute_fn)
        assert result.model_used == "model-a"
        assert result.fallback_from is None
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_fallback_on_500(self):
        executor = FallbackExecutor()
        call_count = 0

        async def execute_fn(model: str):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if model == "model-a":
                resp.status_code = 500
            else:
                resp.status_code = 200
            return resp

        result = await executor.execute(["model-a", "model-b"], execute_fn)
        assert result.model_used == "model-b"
        assert result.fallback_from == "model-a"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_no_fallback_on_400(self):
        """Client errors (400) should NOT trigger fallback."""
        executor = FallbackExecutor()

        async def execute_fn(model: str):
            resp = MagicMock()
            resp.status_code = 400
            return resp

        result = await executor.execute(["model-a", "model-b"], execute_fn)
        assert result.model_used == "model-a"
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_all_models_fail_raises(self):
        executor = FallbackExecutor()

        async def execute_fn(model: str):
            resp = MagicMock()
            resp.status_code = 502
            return resp

        with pytest.raises(AllModelsFailedError) as exc_info:
            await executor.execute(["model-a", "model-b"], execute_fn)

        assert len(exc_info.value.chain) == 2

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        executor = FallbackExecutor()

        async def execute_fn(model: str):
            if model == "model-a":
                raise TimeoutError("read timeout")
            resp = MagicMock()
            resp.status_code = 200
            return resp

        result = await executor.execute(["model-a", "model-b"], execute_fn)
        assert result.model_used == "model-b"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_empty_chain_raises(self):
        executor = FallbackExecutor()

        async def execute_fn(model: str):
            pass

        with pytest.raises(ValueError, match="empty"):
            await executor.execute([], execute_fn)


# ════════════════════════════════════════════════════════════════════
# API endpoint integration tests
# ════════════════════════════════════════════════════════════════════


class TestRouterAPI:
    def test_create_route(self, test_client):
        resp = test_client.post(
            "/api/v1/routes",
            json={
                "name": "test-route",
                "strategy": "complexity",
                "rules": [
                    {"condition": "token_count < 100", "target": "small-model"},
                ],
                "fallback_chain": ["small-model", "large-model"],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "test-route"
        assert body["strategy"] == "complexity"
        assert body["route_id"]

    def test_list_routes(self, test_client):
        # Create two routes
        test_client.post("/api/v1/routes", json={"name": "route-1"})
        test_client.post("/api/v1/routes", json={"name": "route-2"})

        resp = test_client.get("/api/v1/routes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2

    def test_get_route(self, test_client):
        create_resp = test_client.post("/api/v1/routes", json={"name": "get-me"})
        route_id = create_resp.json()["route_id"]

        resp = test_client.get(f"/api/v1/routes/{route_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"

    def test_get_nonexistent_returns_404(self, test_client):
        resp = test_client.get("/api/v1/routes/nonexistent-id")
        assert resp.status_code == 404

    def test_update_route(self, test_client):
        create_resp = test_client.post("/api/v1/routes", json={"name": "original"})
        route_id = create_resp.json()["route_id"]

        resp = test_client.patch(
            f"/api/v1/routes/{route_id}",
            json={"name": "updated", "priority": 50},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        assert resp.json()["priority"] == 50

    def test_delete_route(self, test_client):
        create_resp = test_client.post("/api/v1/routes", json={"name": "delete-me"})
        route_id = create_resp.json()["route_id"]

        resp = test_client.delete(f"/api/v1/routes/{route_id}")
        assert resp.status_code == 204

        # Verify gone
        resp2 = test_client.get(f"/api/v1/routes/{route_id}")
        assert resp2.status_code == 404

    def test_evaluate_dry_run(self, test_client):
        # Create a complexity route
        test_client.post(
            "/api/v1/routes",
            json={
                "name": "eval-route",
                "strategy": "complexity",
                "match": {"endpoint": "/v1/chat/completions", "models": ["*"]},
                "rules": [
                    {"condition": "token_count < 100", "target": "small-model"},
                    {"condition": "token_count >= 100", "target": "large-model"},
                ],
                "priority": 100,
            },
        )

        resp = test_client.post(
            "/api/v1/routes/evaluate",
            json={
                "endpoint": "/v1/chat/completions",
                "model_requested": "any",
                "token_count_estimate": 50,
                "message_count": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model"] == "small-model"
        assert body["strategy"] == "complexity"
