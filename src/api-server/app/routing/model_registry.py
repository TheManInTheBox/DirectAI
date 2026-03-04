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

    Supports two model sources:
    - **Static** — loaded from YAML files at startup (read-only).
    - **Dynamic** — registered at runtime via ``register_dynamic()``
      when a deployment transitions to running.

    Usage:
        registry = ModelRegistry.from_directory(Path("/app/models"))
        spec = registry.resolve("llama-3.1-70b-instruct")
        spec.backend_url  # http://llama-3-1-70b-instruct.directai.svc.cluster.local:8001
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelSpec] = {}      # name → spec
        self._alias_index: dict[str, str] = {}        # alias → name
        self._dynamic: set[str] = set()               # names of dynamically registered models

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
        if not registry._models:
            logger.warning(
                "⚠ Zero models loaded from %s — /v1/models will be empty. "
                "Did you forget to mount model configs via Helm modelConfigs or --set-file?",
                config_dir,
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
        from app.telemetry import get_tracer

        tracer = get_tracer()
        with tracer.start_as_current_span(
            "model_registry.resolve",
            attributes={"directai.model.requested": model_name},
        ) as span:
            name = self._alias_index.get(model_name.lower())
            if name is None:
                span.set_attribute("directai.model.resolved", False)
                return None
            spec = self._models[name]
            span.set_attribute("directai.model.resolved", True)
            span.set_attribute("directai.model.name", spec.name)
            span.set_attribute("directai.model.modality", spec.modality)
            span.set_attribute("directai.model.backend_url", spec.backend_url)
            return spec

    def list_models(self) -> list[ModelSpec]:
        """Return all registered models."""
        return list(self._models.values())

    def register_dynamic(self, spec: ModelSpec) -> None:
        """Add a dynamically deployed model to the routing table.

        Called when a deployment transitions to 'running'.  Overwrites
        any existing dynamic model with the same name (redeployment).
        """
        old_spec = self._models.get(spec.name)
        if old_spec and spec.name in self._dynamic:
            for alias in old_spec.aliases:
                self._alias_index.pop(alias.lower(), None)

        self._models[spec.name] = spec
        for alias in spec.aliases:
            lower = alias.lower()
            if lower in self._alias_index and self._alias_index[lower] != spec.name:
                logger.warning(
                    "Dynamic model alias '%s' shadows existing model '%s'",
                    alias, self._alias_index[lower],
                )
            self._alias_index[lower] = spec.name
        self._dynamic.add(spec.name)
        logger.info("Registered dynamic model: %s (%d aliases)", spec.name, len(spec.aliases))

    def unregister_dynamic(self, name: str) -> bool:
        """Remove a dynamically registered model from the routing table.

        Returns True if removed.  Only dynamic models can be
        unregistered — YAML-loaded models are permanent.
        """
        if name not in self._dynamic:
            return False
        spec = self._models.pop(name, None)
        if spec:
            for alias in spec.aliases:
                if self._alias_index.get(alias.lower()) == name:
                    del self._alias_index[alias.lower()]
        self._dynamic.discard(name)
        logger.info("Unregistered dynamic model: %s", name)
        return True

    def __len__(self) -> int:
        return len(self._models)
