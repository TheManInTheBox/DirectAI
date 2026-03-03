"""
DirectAI-native API — System endpoints.

GET /api/v1/health      Service health snapshot
GET /api/v1/gpu-pools   GPU pool capacity summary
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Request

from app.auth import require_api_key
from app.models.domain import DeploymentStatus
from app.schemas.native import (
    GpuPoolInfo,
    GpuPoolListResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api/v1", tags=["system-native"])

# Startup timestamp — set once when the module loads. The lifespan
# hasn't run yet at import time so we re-assign in the health handler
# on first call, but this gives a reasonable fallback.
_STARTUP_TIME: float = time.monotonic()


def _set_startup_time() -> None:
    """Called from lifespan to record exact startup moment."""
    global _STARTUP_TIME  # noqa: PLW0603
    _STARTUP_TIME = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Versioned service health — model counts, deployment counts, uptime."""
    registry = request.app.state.model_registry
    repo = request.app.state.model_repository

    model_count = len(await repo.list_models())
    deployment_count = len(await repo.list_deployments())
    running_count = len(
        await repo.list_deployments(status=DeploymentStatus.RUNNING.value),
    )

    monitor = getattr(request.app.state, "health_monitor", None)
    backend_health = monitor.summary() if monitor else {}

    return HealthResponse(
        status="healthy",
        version=request.app.version,
        uptime_seconds=round(time.monotonic() - _STARTUP_TIME, 1),
        models_registered=model_count,
        models_routable=len(registry),
        deployments_total=deployment_count,
        deployments_running=running_count,
        backends=backend_health,
    )


@router.get("/gpu-pools", response_model=GpuPoolListResponse)
async def gpu_pools(
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """GPU pool capacity summary.

    Aggregates GPU SKU requirements from registered models and
    active deployments to show what pools exist and their utilisation.
    """
    repo = request.app.state.model_repository

    # 1. Gather static (YAML) models — these represent *configured* pools.
    pools: dict[str, dict] = defaultdict(lambda: {
        "gpu_sku": "",
        "models_registered": 0,
        "deployments_running": 0,
        "total_gpu_allocated": 0,
        "min_replicas_sum": 0,
        "max_replicas_sum": 0,
    })

    # Static models from YAML registry — we only know sku from ModelSpec
    # indirectly via the model deployment YAMLs. Pull from native repo.
    registered_models = await repo.list_models()
    for m in registered_models:
        sku = m["required_gpu_sku"]
        pools[sku]["gpu_sku"] = sku
        pools[sku]["models_registered"] += 1

    # 2. Walk deployments to count running + GPU allocation.
    all_deployments = await repo.list_deployments()
    # Build model_id → model lookup for TP degree + SKU.
    model_lookup = {m["id"]: m for m in registered_models}

    for dep in all_deployments:
        model = model_lookup.get(dep["model_id"])
        if model is None:
            continue
        sku = model["required_gpu_sku"]
        pools[sku]["gpu_sku"] = sku
        if dep["status"] == DeploymentStatus.RUNNING.value:
            pools[sku]["deployments_running"] += 1
            # Each running replica uses tp_degree GPUs.  For the
            # allocation estimate we assume min_replicas are active.
            active_replicas = dep["min_replicas"]
            pools[sku]["total_gpu_allocated"] += active_replicas * model["tp_degree"]
        pools[sku]["min_replicas_sum"] += dep["min_replicas"]
        pools[sku]["max_replicas_sum"] += dep["max_replicas"]

    pool_list = [
        GpuPoolInfo(**info)
        for info in sorted(pools.values(), key=lambda p: p["gpu_sku"])
    ]
    return GpuPoolListResponse(data=pool_list, count=len(pool_list))
