"""
DirectAI-native API — Model lifecycle management.

POST   /api/v1/models           Register a new model version
GET    /api/v1/models           List models (filterable by status/arch/modality)
GET    /api/v1/models/{id}      Get model details
PATCH  /api/v1/models/{id}      Update status / engine artifacts (build callback)
DELETE /api/v1/models/{id}      Deregister a model (blocks if active deployments)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import require_api_key
from app.models.domain import Modality, ModelStatus
from app.schemas.native import (
    ModelListResponse,
    ModelResponse,
    RegisterModelRequest,
    UpdateModelRequest,
)

router = APIRouter(prefix="/api/v1", tags=["models-native"])


@router.post("/models", response_model=ModelResponse, status_code=201)
async def register_model(
    body: RegisterModelRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Register a new model version.

    Returns 409 if (name, version) already exists — versions are
    immutable, create a new version instead.
    """
    repo = request.app.state.model_repository
    try:
        model = await repo.register_model(
            name=body.name,
            version=body.version,
            architecture=body.architecture,
            parameter_count=body.parameter_count,
            quantization=body.quantization,
            format=body.format,
            modality=body.modality.value,
            weight_uri=body.weight_uri,
            required_gpu_sku=body.required_gpu_sku,
            tp_degree=body.tp_degree,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return model


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    request: Request,
    status: ModelStatus | None = Query(default=None),  # noqa: B008
    architecture: str | None = Query(default=None),  # noqa: B008
    modality: Modality | None = Query(default=None),  # noqa: B008
    _api_key: str = Depends(require_api_key),
):
    """List all registered models with optional filters."""
    repo = request.app.state.model_repository
    models = await repo.list_models(
        status=status.value if status else None,
        architecture=architecture,
        modality=modality.value if modality else None,
    )
    return ModelListResponse(data=models, count=len(models))


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Get a model by ID."""
    repo = request.app.state.model_repository
    model = await repo.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return model


@router.patch("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    body: UpdateModelRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Update model status or engine artifacts (build pipeline callback).

    Only ``status`` and ``engine_artifacts`` are mutable — all other
    fields are frozen once registered.
    """
    if body.status is None and body.engine_artifacts is None:
        raise HTTPException(status_code=422, detail="Nothing to update — provide status or engine_artifacts.")
    repo = request.app.state.model_repository
    model = await repo.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    updated = await repo.update_model_status(
        model_id,
        status=body.status or ModelStatus(model["status"]),
        engine_artifacts=body.engine_artifacts,
    )
    return updated


@router.delete("/models/{model_id}", response_model=ModelResponse)
async def delete_model(
    model_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Deregister a model.  Fails if active deployments exist."""
    repo = request.app.state.model_repository
    try:
        model = await repo.delete_model(model_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return model
