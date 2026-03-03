"""
Pydantic schemas for the DirectAI-native API.

/api/v1/models       — Model lifecycle management
/api/v1/deployments  — Deployment management

These schemas define the request/response contracts for the native API.
The OpenAI-compatible schemas live in their own modules; these are
purpose-built for DirectAI's model lifecycle and deployment capabilities.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.domain import DeploymentStatus, Modality, ModelStatus, ScalingTier

# ── Models ──────────────────────────────────────────────────────────


class RegisterModelRequest(BaseModel):
    """POST /api/v1/models — register a new model version."""

    name: str = Field(
        ..., min_length=1, max_length=256,
        description="Model name (e.g., 'llama-3.1-70b-instruct').",
    )
    version: str = Field(
        ..., min_length=1, max_length=64,
        description="Version string (e.g., '1.0', 'v2024.03'). Immutable once registered.",
    )
    architecture: str = Field(
        ..., min_length=1, max_length=64,
        description="Model architecture (e.g., 'llama', 'qwen', 'whisper', 'bert').",
    )
    parameter_count: int = Field(
        default=0, ge=0,
        description="Number of parameters (e.g., 70000000000 for 70B).",
    )
    quantization: str = Field(
        default="fp16",
        description="Quantization format (fp16, int8, int4, etc.).",
    )
    format: str = Field(
        default="safetensors",
        description="Weight format (safetensors, onnx, checkpoint).",
    )
    modality: Modality = Field(
        ...,
        description="Inference modality.",
    )
    weight_uri: str = Field(
        ..., min_length=1,
        description="URI to model weights (az://, hf://, s3://).",
    )
    required_gpu_sku: str = Field(
        ..., min_length=1,
        description="Azure VM SKU (e.g., 'Standard_ND96asr_v4').",
    )
    tp_degree: int = Field(
        default=1, ge=1, le=8,
        description="Tensor parallelism degree (1 = single GPU).",
    )


class UpdateModelRequest(BaseModel):
    """PATCH /api/v1/models/{id} — update model status (build pipeline callback).

    Only ``status`` and ``engine_artifacts`` are mutable.  Everything
    else is immutable once registered — create a new version instead.
    """

    status: ModelStatus | None = Field(
        default=None,
        description="New lifecycle status.",
    )
    engine_artifacts: dict[str, str] | None = Field(
        default=None,
        description="Map of GPU SKU → compiled engine blob URI.",
    )


class ModelResponse(BaseModel):
    """Model record returned by all model endpoints."""

    id: str
    name: str
    version: str
    architecture: str
    parameter_count: int
    quantization: str
    format: str
    modality: str
    weight_uri: str
    required_gpu_sku: str
    tp_degree: int
    status: ModelStatus
    engine_artifacts: dict[str, str]
    created_at: str
    updated_at: str


class ModelListResponse(BaseModel):
    """GET /api/v1/models response."""

    data: list[ModelResponse]
    count: int


# ── Deployments ─────────────────────────────────────────────────────


class CreateDeploymentRequest(BaseModel):
    """POST /api/v1/deployments — create a new deployment."""

    model_id: str = Field(..., description="ID of the model to deploy.")
    scaling_tier: ScalingTier = Field(
        default=ScalingTier.ALWAYS_WARM,
        description="Autoscaling tier.",
    )
    min_replicas: int = Field(default=1, ge=0, description="Minimum replicas (0 for scale-to-zero).")
    max_replicas: int = Field(default=4, ge=1, description="Maximum replicas.")
    target_concurrency: int = Field(default=8, ge=1, description="Target in-flight requests per replica.")


class UpdateDeploymentRequest(BaseModel):
    """PATCH /api/v1/deployments/{id} — update scaling config or status.

    Status updates are used by the deploy workflow to report progress:
    ``pending → provisioning → running`` or ``→ failed``.

    When transitioning to ``running``, also set ``endpoint_url`` so the
    model can be registered in the routing table for inference traffic.
    """

    scaling_tier: ScalingTier | None = None
    min_replicas: int | None = Field(default=None, ge=0)
    max_replicas: int | None = Field(default=None, ge=1)
    target_concurrency: int | None = Field(default=None, ge=1)
    status: DeploymentStatus | None = Field(
        default=None,
        description="New deployment status (used by workflow callbacks).",
    )
    endpoint_url: str | None = Field(
        default=None,
        description="Backend URL — set when deployment reaches 'running'.",
    )


class DeploymentResponse(BaseModel):
    """Deployment record returned by all deployment endpoints."""

    id: str
    model_id: str
    scaling_tier: str
    min_replicas: int
    max_replicas: int
    target_concurrency: int
    status: DeploymentStatus
    endpoint_url: str | None
    created_at: str
    updated_at: str
    status_url: str | None = Field(
        default=None,
        description="Pollable URL for tracking deployment status.",
    )

    @model_validator(mode="before")
    @classmethod
    def _populate_status_url(cls, data: Any) -> Any:
        """Auto-populate status_url from id if not already set."""
        if isinstance(data, dict) and data.get("id") and not data.get("status_url"):
            data["status_url"] = f"/api/v1/deployments/{data['id']}"
        return data


class DeploymentListResponse(BaseModel):
    """GET /api/v1/deployments response."""

    data: list[DeploymentResponse]
    count: int


# ── System ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """GET /api/v1/health — service health snapshot."""

    status: str = Field(description="'healthy' or 'degraded'.")
    version: str = Field(description="API server version string.")
    uptime_seconds: float = Field(description="Seconds since startup.")
    models_registered: int = Field(description="Total models in registry (native API).")
    models_routable: int = Field(description="Models available for inference.")
    deployments_total: int = Field(description="All deployments (any status).")
    deployments_running: int = Field(description="Deployments in 'running' status.")
    backends: dict[str, Any] = Field(
        default_factory=dict,
        description="Backend health summary from health monitor.",
    )


class GpuPoolInfo(BaseModel):
    """GPU pool capacity summary for a single SKU."""

    gpu_sku: str = Field(description="Azure VM SKU (e.g., Standard_ND96asr_v4).")
    models_registered: int = Field(description="Models registered for this SKU.")
    deployments_running: int = Field(description="Running deployments on this SKU.")
    total_gpu_allocated: int = Field(description="Estimated GPUs allocated (running replicas × TP degree).")
    min_replicas_sum: int = Field(description="Sum of min_replicas across all deployments.")
    max_replicas_sum: int = Field(description="Sum of max_replicas across all deployments.")


class GpuPoolListResponse(BaseModel):
    """GET /api/v1/gpu-pools response."""

    data: list[GpuPoolInfo]
    count: int


# ── Engine Cache ────────────────────────────────────────────────────


class RegisterEngineCacheRequest(BaseModel):
    """POST /api/v1/engine-cache — register a compiled engine."""

    architecture: str = Field(..., min_length=1, max_length=64,
                               description="Model architecture (e.g., 'llama', 'qwen', 'whisper').")
    parameter_count: str = Field(..., min_length=1, max_length=32,
                                  description="Parameter count label (e.g., '7b', '70b', 'large-v3').")
    quantization: str = Field(default="float16",
                               description="Quantization / dtype (float16, bfloat16, int8, int4_awq).")
    tp_degree: int = Field(default=1, ge=1, le=8,
                            description="Tensor parallelism degree the engine was compiled for.")
    gpu_sku: str = Field(..., min_length=1,
                          description="Azure VM SKU (e.g., 'Standard_ND96asr_v4').")
    trtllm_version: str = Field(..., min_length=1,
                                 description="TRT-LLM version used for compilation (e.g., '0.16.0').")
    engine_uri: str = Field(..., min_length=1,
                             description="Full Blob URI of compiled engine artifacts.")


class EngineCacheEntry(BaseModel):
    """Single cached engine entry."""

    id: str
    cache_key: str
    architecture: str
    parameter_count: str
    quantization: str
    tp_degree: int
    gpu_sku: str
    trtllm_version: str
    engine_uri: str
    created_at: str
    updated_at: str


class EngineCacheListResponse(BaseModel):
    """GET /api/v1/engine-cache response."""

    data: list[EngineCacheEntry]
    count: int


class EngineCacheLookupResponse(BaseModel):
    """GET /api/v1/engine-cache/lookup response."""

    cache_hit: bool = Field(description="True if a matching engine was found.")
    cache_key: str = Field(description="The computed cache key for the query.")
    entry: EngineCacheEntry | None = Field(
        default=None, description="The cached engine entry, or null on miss.",
    )
