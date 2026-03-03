"""
DirectAI-native API — Deployment management.

POST   /api/v1/deployments           Create a deployment
GET    /api/v1/deployments           List deployments (filterable)
GET    /api/v1/deployments/{id}      Deployment details
PATCH  /api/v1/deployments/{id}      Update scaling config or status
DELETE /api/v1/deployments/{id}      Terminate a deployment

Routing integration
-------------------
When a deployment transitions to ``running`` with an ``endpoint_url``,
the model is automatically registered in the routing table and becomes
available for inference via the OpenAI-compatible /v1/* endpoints.

When a deployment is terminated or fails, the model is removed from
the routing table.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import require_api_key
from app.models.domain import DeploymentStatus, ModelStatus
from app.routing import ModelSpec
from app.schemas.native import (
    CreateDeploymentRequest,
    DeploymentListResponse,
    DeploymentResponse,
    UpdateDeploymentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["deployments-native"])


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/deployments", response_model=DeploymentResponse, status_code=201)
async def create_deployment(
    body: CreateDeploymentRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Create a new deployment for a registered model.

    The deployment starts in ``pending`` status.  The deploy workflow
    (or operator) should PATCH status through provisioning → running.
    """
    repo = request.app.state.model_repository
    try:
        deployment = await repo.create_deployment(
            model_id=body.model_id,
            scaling_tier=body.scaling_tier.value,
            min_replicas=body.min_replicas,
            max_replicas=body.max_replicas,
            target_concurrency=body.target_concurrency,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return deployment


@router.get("/deployments", response_model=DeploymentListResponse)
async def list_deployments(
    request: Request,
    status: DeploymentStatus | None = Query(default=None),  # noqa: B008
    model_id: str | None = Query(default=None),  # noqa: B008
    _api_key: str = Depends(require_api_key),
):
    """List deployments with optional filters."""
    repo = request.app.state.model_repository
    deployments = await repo.list_deployments(
        status=status.value if status else None,
        model_id=model_id,
    )
    return DeploymentListResponse(data=deployments, count=len(deployments))


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Get deployment details."""
    repo = request.app.state.model_repository
    deployment = await repo.get_deployment(deployment_id)
    if deployment is None:
        raise HTTPException(
            status_code=404, detail=f"Deployment '{deployment_id}' not found.",
        )
    return deployment


@router.patch("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: str,
    body: UpdateDeploymentRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Update deployment scaling config or status.

    Status transitions are used by the deploy workflow to report
    progress: ``pending → provisioning → running`` or ``→ failed``.

    When status transitions to ``running`` **and** ``endpoint_url`` is
    provided, the model is added to the inference routing table.
    """
    repo = request.app.state.model_repository
    existing = await repo.get_deployment(deployment_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Deployment '{deployment_id}' not found.",
        )

    updates = body.model_dump(exclude_none=True)
    if "status" in updates:
        updates["status"] = updates["status"].value
    if "scaling_tier" in updates:
        updates["scaling_tier"] = updates["scaling_tier"].value

    deployment = await repo.update_deployment(deployment_id, **updates)

    # ── Routing integration ─────────────────────────────────────
    if body.status == DeploymentStatus.RUNNING and body.endpoint_url:
        await _register_in_router(request, deployment)  # type: ignore[arg-type]
    elif body.status in (DeploymentStatus.TERMINATED, DeploymentStatus.FAILED):
        await _unregister_from_router(request, existing["model_id"])

    return deployment


@router.delete("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def delete_deployment(
    deployment_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Terminate a deployment and remove from routing."""
    repo = request.app.state.model_repository
    existing = await repo.get_deployment(deployment_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Deployment '{deployment_id}' not found.",
        )
    deployment = await repo.delete_deployment(deployment_id)
    await _unregister_from_router(request, existing["model_id"])
    return deployment


# ── Routing helpers ─────────────────────────────────────────────────


async def _register_in_router(
    request: Request,
    deployment: dict,
) -> None:
    """Add a deployed model to the inference routing table."""
    repo = request.app.state.model_repository
    registry = request.app.state.model_registry
    model = await repo.get_model(deployment["model_id"])
    if model is None:
        return
    engine_type = "onnxruntime" if model["modality"] == "embedding" else "tensorrt-llm"
    spec = ModelSpec(
        name=model["name"],
        display_name=f"{model['name']} v{model['version']}",
        owned_by="directai",
        modality=model["modality"],
        engine_type=engine_type,
        backend_url=deployment["endpoint_url"].rstrip("/"),
        aliases=[model["name"]],
    )
    registry.register_dynamic(spec)
    # Also update model status to deployed
    await repo.update_model_status(model["id"], ModelStatus.DEPLOYED)
    logger.info(
        "Model '%s' v%s registered in router → %s",
        model["name"], model["version"], deployment["endpoint_url"],
    )


async def _unregister_from_router(
    request: Request,
    model_id: str,
) -> None:
    """Remove a model from the inference routing table."""
    repo = request.app.state.model_repository
    registry = request.app.state.model_registry
    model = await repo.get_model(model_id)
    if model is None:
        return
    removed = registry.unregister_dynamic(model["name"])
    if removed:
        logger.info("Model '%s' removed from router.", model["name"])
