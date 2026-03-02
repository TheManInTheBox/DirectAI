"""
Model registry — loads ModelDeployment YAML files and provides lookup.

The registry is the single source of truth for:
  - Which models are available
  - What modality each model serves (chat, embedding, transcription)
  - The backend service URL for each model
  - Model metadata returned by GET /v1/models

In-cluster, each model backend is a K8s Service named after the model.
The service URL pattern is: http://{model-name}.{namespace}.svc.cluster.local:{port}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    """Parsed model deployment spec."""

    name: str
    display_name: str
    owned_by: str
    modality: Literal["chat", "embedding", "transcription"]
    engine_type: str
    backend_url: str
    aliases: list[str] = field(default_factory=list)


class ModelRegistry:
    """
    Loads model configs from YAML files and provides lookup by alias.

    Usage:
        registry = ModelRegistry.from_directory(Path("/app/models"))
        spec = registry.resolve("llama-3.1-70b-instruct")
        spec.backend_url  # http://llama-3-1-70b-instruct.directai.svc.cluster.local:8001
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelSpec] = {}      # name → spec
        self._alias_index: dict[str, str] = {}        # alias → name

    @classmethod
    def from_directory(
        cls,
        config_dir: Path,
        namespace: str = "directai",
        backend_port: int = 8001,
    ) -> ModelRegistry:
        """Load all .yaml/.yml files from a directory."""
        registry = cls()
        if not config_dir.is_dir():
            logger.warning("Model config directory does not exist: %s", config_dir)
            return registry

        for path in sorted(config_dir.glob("*.yaml")) + sorted(config_dir.glob("*.yml")):
            try:
                registry._load_file(path, namespace, backend_port)
            except Exception:
                logger.exception("Failed to load model config: %s", path)
        logger.info(
            "Model registry loaded: %d models, %d aliases",
            len(registry._models),
            len(registry._alias_index),
        )
        return registry

    def _load_file(self, path: Path, namespace: str, backend_port: int) -> None:
        with open(path) as f:
            doc = yaml.safe_load(f)

        if not doc or doc.get("kind") != "ModelDeployment":
            return

        metadata = doc["metadata"]
        spec = doc["spec"]
        name = metadata["name"]

        # Allow explicit backend URL override (local dev).
        # Falls back to K8s service DNS pattern for in-cluster.
        explicit_url = spec.get("engine", {}).get("backendUrl")
        if explicit_url:
            backend_url = explicit_url.rstrip("/")
        else:
            service_name = name.replace(".", "-").replace("_", "-")
            backend_url = f"http://{service_name}.{namespace}.svc.cluster.local:{backend_port}"

        aliases = spec.get("api", {}).get("aliases", [name])

        model_spec = ModelSpec(
            name=name,
            display_name=spec.get("displayName", name),
            owned_by=spec.get("ownedBy", "unknown"),
            modality=spec["modality"],
            engine_type=spec["engine"]["type"],
            backend_url=backend_url,
            aliases=aliases,
        )

        self._models[name] = model_spec
        for alias in aliases:
            lower_alias = alias.lower()
            if lower_alias in self._alias_index:
                logger.warning(
                    "Duplicate model alias '%s': %s vs %s",
                    alias,
                    self._alias_index[lower_alias],
                    name,
                )
            self._alias_index[lower_alias] = name

    def resolve(self, model_name: str) -> ModelSpec | None:
        """Resolve a client-provided model name to a ModelSpec."""
        name = self._alias_index.get(model_name.lower())
        if name is None:
            return None
        return self._models[name]

    def list_models(self) -> list[ModelSpec]:
        """Return all registered models."""
        return list(self._models.values())

    def __len__(self) -> int:
        return len(self._models)
