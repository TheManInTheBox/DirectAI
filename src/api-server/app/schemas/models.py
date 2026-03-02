"""
Pydantic models for GET /v1/models response.

Reference: https://platform.openai.com/docs/api-reference/models
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]
