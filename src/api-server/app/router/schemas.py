"""
Route configuration and routing decision models.

All route config is stored as JSONB in SQLite/PostgreSQL. These Pydantic
models define the shape of route rules, match conditions, A/B test splits,
cost budgets, and the resulting routing decision.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────


class RoutingStrategy(str, Enum):
    """Supported routing strategies."""

    DIRECT = "direct"
    COMPLEXITY = "complexity"
    COST = "cost"
    LATENCY = "latency"
    RANDOM = "random"
    FALLBACK = "fallback"


# ── Route configuration sub-models ─────────────────────────────────


class MatchConfig(BaseModel):
    """Conditions that determine whether a route applies to a request."""

    endpoint: str = Field(
        default="/v1/chat/completions",
        description="Request path to match (exact).",
    )
    models: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Model names/globs to match. ['*'] matches all.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Required request headers (key=value).",
    )


class RoutingRule(BaseModel):
    """A single routing rule within a strategy."""

    condition: str = Field(
        description="Evaluation condition (e.g., 'token_count < 100').",
    )
    target: str = Field(
        description="Target model name to route to.",
    )
    weight: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Weight for random/A-B selection (0-100).",
    )


class ABTestConfig(BaseModel):
    """A/B test split configuration."""

    experiment_name: str
    variants: list[ABVariant] = Field(default_factory=list)


class ABVariant(BaseModel):
    """A single A/B test variant."""

    name: str
    model: str
    weight: int = Field(ge=0, le=100, description="Traffic percentage (0-100).")


# Fix forward reference
ABTestConfig.model_rebuild()


class CostBudget(BaseModel):
    """Cost control configuration for a route."""

    daily_limit_usd: float = Field(gt=0, description="Max daily spend in USD.")
    action_on_exceed: str = Field(
        default="downgrade",
        description="Action when budget exceeded: 'downgrade' | 'reject' | 'alert'.",
    )


# ── Route configuration (full) ─────────────────────────────────────


class RouteConfig(BaseModel):
    """Complete route configuration — the unit of storage."""

    route_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    customer_id: str = Field(default="default")
    match: MatchConfig = Field(default_factory=MatchConfig)
    strategy: RoutingStrategy = RoutingStrategy.DIRECT
    rules: list[RoutingRule] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    ab_test: Optional[ABTestConfig] = None
    cost_budget: Optional[CostBudget] = None
    enabled: bool = True
    priority: int = Field(default=0, description="Higher = evaluated first.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RouteCreate(BaseModel):
    """Request body for creating a route."""

    name: str
    customer_id: str = "default"
    match: MatchConfig = Field(default_factory=MatchConfig)
    strategy: RoutingStrategy = RoutingStrategy.DIRECT
    rules: list[RoutingRule] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    ab_test: Optional[ABTestConfig] = None
    cost_budget: Optional[CostBudget] = None
    enabled: bool = True
    priority: int = 0


class RouteUpdate(BaseModel):
    """Request body for updating a route (all fields optional)."""

    name: Optional[str] = None
    match: Optional[MatchConfig] = None
    strategy: Optional[RoutingStrategy] = None
    rules: Optional[list[RoutingRule]] = None
    fallback_chain: Optional[list[str]] = None
    ab_test: Optional[ABTestConfig] = None
    cost_budget: Optional[CostBudget] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class RouteListResponse(BaseModel):
    """Response for listing routes."""

    routes: list[RouteConfig]
    total: int


# ── Routing decision (output) ──────────────────────────────────────


class RoutingDecision(BaseModel):
    """The result of evaluating routing rules for a request."""

    model: str = Field(description="Target model name to proxy to.")
    fallback_chain: list[str] = Field(
        default_factory=list,
        description="Remaining fallback models if primary fails.",
    )
    ab_variant: Optional[str] = Field(
        default=None,
        description="A/B test variant name if applicable.",
    )
    route_id: Optional[str] = Field(
        default=None,
        description="Route config ID that produced this decision.",
    )
    strategy: str = Field(
        default="direct",
        description="Strategy that was used.",
    )


# ── Inference request context (for strategy evaluation) ─────────────


class InferenceContext(BaseModel):
    """Request context used by routing strategies to make decisions."""

    endpoint: str
    model_requested: str
    token_count_estimate: int = 0
    message_count: int = 0
    headers: dict[str, str] = Field(default_factory=dict)
    customer_id: str = "default"
