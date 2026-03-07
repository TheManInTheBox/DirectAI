"""
Model Router — intelligent request routing with fallback chains.

Evaluates route configurations to select the optimal backend model for
each request based on complexity, cost, latency, or weighted-random
strategies. Includes circuit-breaker–protected fallback chains for
high availability.

Public surface:
  - ``RoutingEngine``   — evaluates routes and returns RoutingDecision
  - ``FallbackExecutor`` — runs fallback chains with circuit breaker
  - ``RouteRepository``  — SQLite CRUD for route configs
  - ``router_api``       — FastAPI router for /api/v1/routes CRUD
"""

from app.router.engine import RoutingEngine
from app.router.fallback import FallbackExecutor
from app.router.repository import RouteRepository
from app.router.routes import router as router_api

__all__ = [
    "FallbackExecutor",
    "RouteRepository",
    "RoutingEngine",
    "router_api",
]
