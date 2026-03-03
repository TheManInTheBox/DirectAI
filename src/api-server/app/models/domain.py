"""
Domain enumerations for model lifecycle management.

These enums define the valid states for models, deployments, scaling
tiers, and modalities.  They are used by the repository, schemas,
and route handlers — never import raw strings when an enum exists.
"""

from __future__ import annotations

import enum


class ModelStatus(enum.StrEnum):
    """Model lifecycle status."""

    REGISTERED = "registered"
    BUILDING = "building"
    READY = "ready"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DeploymentStatus(enum.StrEnum):
    """Deployment lifecycle status."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    FAILED = "failed"
    TERMINATED = "terminated"


class ScalingTier(enum.StrEnum):
    """Autoscaling tier for a deployment."""

    ALWAYS_WARM = "always-warm"
    SCALE_TO_ZERO = "scale-to-zero"


class Modality(enum.StrEnum):
    """Inference modality."""

    CHAT = "chat"
    EMBEDDING = "embedding"
    TRANSCRIPTION = "transcription"
