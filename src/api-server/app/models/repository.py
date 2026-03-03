"""
SQLite-backed repository for model and deployment lifecycle.

Clean async interface.  Swap SQLite for PostgreSQL / Cosmos DB when
the need arises — callers only see the public methods, not SQL.

Tables
------
models       — registered model versions with lifecycle status
deployments  — deployment records tracking K8s endpoint provisioning
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from app.models.domain import DeploymentStatus, ModelStatus

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS models (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    version           TEXT NOT NULL,
    architecture      TEXT NOT NULL,
    parameter_count   INTEGER NOT NULL DEFAULT 0,
    quantization      TEXT NOT NULL DEFAULT 'fp16',
    format            TEXT NOT NULL DEFAULT 'safetensors',
    modality          TEXT NOT NULL,
    weight_uri        TEXT NOT NULL,
    required_gpu_sku  TEXT NOT NULL,
    tp_degree         INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'registered',
    engine_artifacts  TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS deployments (
    id                 TEXT PRIMARY KEY,
    model_id           TEXT NOT NULL REFERENCES models(id),
    scaling_tier       TEXT NOT NULL DEFAULT 'always-warm',
    min_replicas       INTEGER NOT NULL DEFAULT 1,
    max_replicas       INTEGER NOT NULL DEFAULT 4,
    target_concurrency INTEGER NOT NULL DEFAULT 8,
    status             TEXT NOT NULL DEFAULT 'pending',
    endpoint_url       TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
"""

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_model(row: aiosqlite.Row) -> dict[str, Any]:
    d = dict(row)
    d["engine_artifacts"] = json.loads(d["engine_artifacts"])
    return d


def _row_to_deployment(row: aiosqlite.Row) -> dict[str, Any]:
    return dict(row)


# ------------------------------------------------------------------
# Repository
# ------------------------------------------------------------------


class ModelRepository:
    """Async SQLite repository for models and deployments."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ── Lifecycle ───────────────────────────────────────────────────

    async def startup(self) -> None:
        """Open DB connection and ensure schema exists."""
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        logger.info("Model repository opened: %s", self._db_path)

    async def shutdown(self) -> None:
        """Close DB connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Repository not started — call startup() first.")
        return self._db

    # ── Models ──────────────────────────────────────────────────────

    async def register_model(
        self,
        *,
        name: str,
        version: str,
        architecture: str,
        parameter_count: int = 0,
        quantization: str = "fp16",
        format: str = "safetensors",
        modality: str,
        weight_uri: str,
        required_gpu_sku: str,
        tp_degree: int = 1,
    ) -> dict[str, Any]:
        """Register a new model version.

        Raises ``ValueError`` if (name, version) already exists.
        Versions are immutable — register a new version instead.
        """
        model_id = _new_id()
        now = _now()
        try:
            await self._conn.execute(
                """
                INSERT INTO models
                    (id, name, version, architecture, parameter_count,
                     quantization, format, modality, weight_uri,
                     required_gpu_sku, tp_degree, status, engine_artifacts,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id, name, version, architecture, parameter_count,
                    quantization, format, modality, weight_uri,
                    required_gpu_sku, tp_degree, ModelStatus.REGISTERED.value,
                    "{}", now, now,
                ),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError as exc:
            raise ValueError(
                f"Model '{name}' version '{version}' already exists. "
                "Versions are immutable — register a new version instead."
            ) from exc
        return await self.get_model(model_id)  # type: ignore[return-value]

    async def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Fetch a model by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM models WHERE id = ?", (model_id,)
        )
        row = await cursor.fetchone()
        return _row_to_model(row) if row else None

    async def get_model_by_name_version(
        self, name: str, version: str,
    ) -> dict[str, Any] | None:
        """Fetch a model by (name, version) pair."""
        cursor = await self._conn.execute(
            "SELECT * FROM models WHERE name = ? AND version = ?",
            (name, version),
        )
        row = await cursor.fetchone()
        return _row_to_model(row) if row else None

    async def list_models(
        self,
        *,
        status: str | None = None,
        architecture: str | None = None,
        modality: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models with optional filters."""
        query = "SELECT * FROM models WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if architecture:
            query += " AND architecture = ?"
            params.append(architecture)
        if modality:
            query += " AND modality = ?"
            params.append(modality)
        query += " ORDER BY created_at DESC"
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_model(r) for r in rows]

    async def update_model_status(
        self,
        model_id: str,
        status: ModelStatus,
        engine_artifacts: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Update model status and optionally engine artifacts."""
        existing = await self.get_model(model_id)
        if existing is None:
            return None
        now = _now()
        if engine_artifacts is not None:
            await self._conn.execute(
                "UPDATE models SET status = ?, engine_artifacts = ?, updated_at = ? WHERE id = ?",
                (status.value, json.dumps(engine_artifacts), now, model_id),
            )
        else:
            await self._conn.execute(
                "UPDATE models SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, model_id),
            )
        await self._conn.commit()
        return await self.get_model(model_id)

    async def delete_model(self, model_id: str) -> dict[str, Any] | None:
        """Delete a model.  Fails if active deployments exist."""
        model = await self.get_model(model_id)
        if model is None:
            return None
        # Block deletion if there are non-terminal deployments
        cursor = await self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM deployments "
            "WHERE model_id = ? AND status NOT IN (?, ?)",
            (model_id, DeploymentStatus.TERMINATED.value, DeploymentStatus.FAILED.value),
        )
        row = await cursor.fetchone()
        if row and row["cnt"] > 0:
            raise ValueError(
                f"Cannot delete model '{model['name']}' — it has {row['cnt']} "
                "active deployment(s). Terminate all deployments first."
            )
        await self._conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
        await self._conn.commit()
        return model

    # ── Deployments ─────────────────────────────────────────────────

    async def create_deployment(
        self,
        *,
        model_id: str,
        scaling_tier: str = "always-warm",
        min_replicas: int = 1,
        max_replicas: int = 4,
        target_concurrency: int = 8,
    ) -> dict[str, Any]:
        """Create a deployment for a registered model.

        Raises ``ValueError`` if the model doesn't exist or isn't in a
        deployable status.
        """
        model = await self.get_model(model_id)
        if model is None:
            raise ValueError(f"Model '{model_id}' not found.")
        deployable = {
            ModelStatus.REGISTERED.value,
            ModelStatus.READY.value,
            ModelStatus.DEPLOYED.value,
        }
        if model["status"] not in deployable:
            raise ValueError(
                f"Model status is '{model['status']}' — must be one of "
                f"{sorted(deployable)} to create a deployment."
            )
        deployment_id = _new_id()
        now = _now()
        await self._conn.execute(
            """
            INSERT INTO deployments
                (id, model_id, scaling_tier, min_replicas, max_replicas,
                 target_concurrency, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deployment_id, model_id, scaling_tier, min_replicas,
                max_replicas, target_concurrency,
                DeploymentStatus.PENDING.value, now, now,
            ),
        )
        await self._conn.commit()
        return await self.get_deployment(deployment_id)  # type: ignore[return-value]

    async def get_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        """Fetch a deployment by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
        )
        row = await cursor.fetchone()
        return _row_to_deployment(row) if row else None

    async def list_deployments(
        self,
        *,
        status: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List deployments with optional filters."""
        query = "SELECT * FROM deployments WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        query += " ORDER BY created_at DESC"
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_deployment(r) for r in rows]

    async def update_deployment(
        self, deployment_id: str, **updates: Any,
    ) -> dict[str, Any] | None:
        """Update mutable deployment fields."""
        existing = await self.get_deployment(deployment_id)
        if existing is None:
            return None
        allowed = {
            "scaling_tier", "min_replicas", "max_replicas",
            "target_concurrency", "status", "endpoint_url",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not filtered:
            return existing
        filtered["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in filtered)
        values = list(filtered.values()) + [deployment_id]
        await self._conn.execute(
            f"UPDATE deployments SET {set_clause} WHERE id = ?",  # noqa: S608
            values,
        )
        await self._conn.commit()
        return await self.get_deployment(deployment_id)

    async def delete_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        """Terminate a deployment (sets status to terminated)."""
        existing = await self.get_deployment(deployment_id)
        if existing is None:
            return None
        return await self.update_deployment(
            deployment_id, status=DeploymentStatus.TERMINATED.value,
        )
