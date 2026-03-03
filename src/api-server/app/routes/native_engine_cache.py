"""
DirectAI-native API — Engine cache management.

Pre-compiled TRT-LLM engine cache for instant deployments.  The cache
is keyed by {architecture}_{parameter_count}_{quantization}_tp{tp_degree}_{gpu_sku}_trtllm{version}.

POST   /api/v1/engine-cache           Register a compiled engine
GET    /api/v1/engine-cache           List cached engines (filterable)
GET    /api/v1/engine-cache/lookup    Look up a cached engine by components
GET    /api/v1/engine-cache/{id}      Get a specific cache entry
DELETE /api/v1/engine-cache/{id}      Remove a cache entry
DELETE /api/v1/engine-cache/version/{trtllm_version}  Invalidate all entries for a version
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import require_api_key
from app.models.repository import build_cache_key
from app.schemas.native import (
    EngineCacheEntry,
    EngineCacheListResponse,
    EngineCacheLookupResponse,
    RegisterEngineCacheRequest,
)

router = APIRouter(prefix="/api/v1", tags=["engine-cache"])


@router.post("/engine-cache", response_model=EngineCacheEntry, status_code=201)
async def register_engine(
    body: RegisterEngineCacheRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Register a compiled engine in the cache (upsert by cache key)."""
    repo = request.app.state.model_repository
    entry = await repo.register_engine(
        architecture=body.architecture,
        parameter_count=body.parameter_count,
        quantization=body.quantization,
        tp_degree=body.tp_degree,
        gpu_sku=body.gpu_sku,
        trtllm_version=body.trtllm_version,
        engine_uri=body.engine_uri,
    )
    return entry


@router.get("/engine-cache", response_model=EngineCacheListResponse)
async def list_engine_cache(
    request: Request,
    architecture: str | None = Query(default=None),
    gpu_sku: str | None = Query(default=None),
    trtllm_version: str | None = Query(default=None),
    _api_key: str = Depends(require_api_key),
):
    """List cached engines with optional filters."""
    repo = request.app.state.model_repository
    entries = await repo.list_engine_cache(
        architecture=architecture,
        gpu_sku=gpu_sku,
        trtllm_version=trtllm_version,
    )
    return EngineCacheListResponse(data=entries, count=len(entries))


@router.get("/engine-cache/lookup", response_model=EngineCacheLookupResponse)
async def lookup_engine(
    request: Request,
    architecture: str = Query(..., description="Model architecture"),
    parameter_count: str = Query(..., description="Parameter count label"),
    quantization: str = Query(default="float16", description="Quantization"),
    tp_degree: int = Query(default=1, ge=1, le=8, description="TP degree"),
    gpu_sku: str = Query(..., description="Target GPU SKU"),
    trtllm_version: str = Query(..., description="TRT-LLM version"),
    _api_key: str = Depends(require_api_key),
):
    """Look up a cached engine by its component fields.

    Returns cache_hit=true with the entry if found, or cache_hit=false
    with entry=null if not.  A version mismatch is treated as a miss
    (lazy invalidation).
    """
    cache_key = build_cache_key(
        architecture, parameter_count, quantization,
        tp_degree, gpu_sku, trtllm_version,
    )
    repo = request.app.state.model_repository
    entry = await repo.lookup_engine(cache_key=cache_key)
    # Lazy invalidation: if the stored entry's version doesn't match, treat as miss
    if entry and entry["trtllm_version"] != trtllm_version:
        entry = None
    return EngineCacheLookupResponse(
        cache_hit=entry is not None,
        cache_key=cache_key,
        entry=entry,
    )


@router.get("/engine-cache/{entry_id}", response_model=EngineCacheEntry)
async def get_engine_cache_entry(
    entry_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Get a specific engine cache entry."""
    repo = request.app.state.model_repository
    entry = await repo.get_engine_cache_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Engine cache entry '{entry_id}' not found.")
    return entry


@router.delete("/engine-cache/{entry_id}", response_model=EngineCacheEntry)
async def delete_engine_cache_entry(
    entry_id: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Delete a specific engine cache entry."""
    repo = request.app.state.model_repository
    entry = await repo.delete_engine_cache_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Engine cache entry '{entry_id}' not found.")
    return entry


@router.delete("/engine-cache/version/{trtllm_version}")
async def invalidate_by_version(
    trtllm_version: str,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    """Invalidate all cached engines for a specific TRT-LLM version.

    Use this for proactive cache busting when the engine cache exceeds
    ~20 entries and lazy invalidation becomes too slow.
    """
    repo = request.app.state.model_repository
    count = await repo.invalidate_engine_cache_by_version(trtllm_version)
    return {"deleted": count, "trtllm_version": trtllm_version}
