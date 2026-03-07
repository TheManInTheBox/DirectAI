"""
Route management API — CRUD endpoints for /api/v1/routes.

Provides route configuration management and a dry-run evaluation
endpoint for testing routing rules without executing real requests.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.router.schemas import (
    InferenceContext,
    RouteConfig,
    RouteCreate,
    RouteListResponse,
    RouteUpdate,
    RoutingDecision,
)

logger = logging.getLogger("directai.router")
router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


@router.post("", response_model=RouteConfig, status_code=201)
async def create_route(body: RouteCreate, request: Request):
    """Create a new route configuration."""
    repo = _get_repo(request)
    config = await repo.create(body)
    logger.info("Route created: %s (%s)", config.name, config.route_id)
    return config


@router.get("", response_model=RouteListResponse)
async def list_routes(
    request: Request,
    customer_id: Optional[str] = None,
):
    """List route configurations, optionally filtered by customer_id."""
    repo = _get_repo(request)
    routes = await repo.list_routes(customer_id=customer_id)
    return RouteListResponse(routes=routes, total=len(routes))


@router.get("/{route_id}", response_model=RouteConfig)
async def get_route(route_id: str, request: Request):
    """Get a single route configuration by ID."""
    repo = _get_repo(request)
    config = await repo.get(route_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found.")
    return config


@router.patch("/{route_id}", response_model=RouteConfig)
async def update_route(route_id: str, body: RouteUpdate, request: Request):
    """Partial update of a route configuration."""
    repo = _get_repo(request)
    config = await repo.update(route_id, body)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found.")
    logger.info("Route updated: %s", route_id)
    return config


@router.delete("/{route_id}", status_code=204)
async def delete_route(route_id: str, request: Request):
    """Delete a route configuration."""
    repo = _get_repo(request)
    deleted = await repo.delete(route_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found.")
    logger.info("Route deleted: %s", route_id)


@router.post("/evaluate", response_model=RoutingDecision)
async def evaluate_route(body: InferenceContext, request: Request):
    """
    Dry-run: evaluate routing rules for a request context.

    Returns the ``RoutingDecision`` that would be made without executing
    the actual inference request. Useful for testing route configurations.
    """
    engine = _get_engine(request)
    decision = engine.resolve(body)
    return decision


def _get_repo(request: Request):
    repo = getattr(request.app.state, "route_repository", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Route repository not initialized.")
    return repo


def _get_engine(request: Request):
    engine = getattr(request.app.state, "routing_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Routing engine not initialized.")
    return engine
