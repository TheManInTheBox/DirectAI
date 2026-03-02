"""
GET /v1/models — OpenAI-compatible model listing endpoint.

Returns all models registered in the model registry.
No auth required (matches OpenAI behavior with valid key — but we
keep the dependency for consistency; in dev mode auth is disabled).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_api_key
from app.schemas.models import ModelListResponse, ModelObject

router = APIRouter()


@router.get(
    "/v1/models",
    response_model=ModelListResponse,
)
async def list_models(
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    registry = request.app.state.model_registry
    models = registry.list_models()

    return ModelListResponse(
        data=[
            ModelObject(
                id=alias,
                owned_by=spec.owned_by,
            )
            for spec in models
            for alias in spec.aliases
        ]
    )
