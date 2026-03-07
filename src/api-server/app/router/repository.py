"""
Route configuration repository — SQLite-backed CRUD.

Stores route configs in the same SQLite database as the model repository.
Routes are loaded into memory at startup and refreshed periodically for
fast evaluation without per-request DB queries.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.router.schemas import RouteConfig, RouteCreate, RouteUpdate

logger = logging.getLogger("directai.router")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS routes (
    route_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL DEFAULT 'default',
    name        TEXT NOT NULL,
    match_config TEXT NOT NULL DEFAULT '{}',
    strategy    TEXT NOT NULL DEFAULT 'direct',
    rules       TEXT NOT NULL DEFAULT '[]',
    fallback_chain TEXT NOT NULL DEFAULT '[]',
    ab_test     TEXT,
    cost_budget TEXT,
    enabled     INTEGER NOT NULL DEFAULT 1,
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_routes_customer
    ON routes(customer_id, enabled, priority DESC);
"""


class RouteRepository:
    """
    SQLite-backed route configuration store.

    Thread-safe via ``check_same_thread=False`` and serialized writes.
    Routes are also cached in-memory for fast evaluation.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._cache: dict[str, list[RouteConfig]] = {}  # customer_id → sorted routes

    async def startup(self) -> None:
        """Open DB connection and create tables."""
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX)
        self._conn.commit()
        await self.refresh_cache()
        logger.info("Route repository ready (%s), %d routes cached", self._db_path, sum(len(v) for v in self._cache.values()))

    async def shutdown(self) -> None:
        """Close DB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def refresh_cache(self) -> None:
        """Reload all enabled routes into memory, sorted by priority DESC."""
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM routes WHERE enabled = 1 ORDER BY priority DESC"
        ).fetchall()

        cache: dict[str, list[RouteConfig]] = {}
        for row in rows:
            config = self._row_to_config(row)
            cache.setdefault(config.customer_id, []).append(config)

        self._cache = cache

    def get_routes_for_customer(self, customer_id: str) -> list[RouteConfig]:
        """Return cached routes for a customer (priority-ordered)."""
        return self._cache.get(customer_id, [])

    async def create(self, data: RouteCreate) -> RouteConfig:
        """Insert a new route config."""
        assert self._conn is not None
        import uuid

        now = datetime.now(timezone.utc).isoformat()
        route_id = str(uuid.uuid4())

        config = RouteConfig(
            route_id=route_id,
            name=data.name,
            customer_id=data.customer_id,
            match=data.match,
            strategy=data.strategy,
            rules=data.rules,
            fallback_chain=data.fallback_chain,
            ab_test=data.ab_test,
            cost_budget=data.cost_budget,
            enabled=data.enabled,
            priority=data.priority,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

        self._conn.execute(
            """INSERT INTO routes
               (route_id, customer_id, name, match_config, strategy, rules,
                fallback_chain, ab_test, cost_budget, enabled, priority,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                config.route_id,
                config.customer_id,
                config.name,
                config.match.model_dump_json(),
                config.strategy.value,
                json.dumps([r.model_dump() for r in config.rules]),
                json.dumps(config.fallback_chain),
                config.ab_test.model_dump_json() if config.ab_test else None,
                config.cost_budget.model_dump_json() if config.cost_budget else None,
                int(config.enabled),
                config.priority,
                now,
                now,
            ),
        )
        self._conn.commit()
        await self.refresh_cache()
        return config

    async def get(self, route_id: str) -> Optional[RouteConfig]:
        """Fetch a single route by ID."""
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM routes WHERE route_id = ?", (route_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_config(row)

    async def list_routes(
        self, customer_id: Optional[str] = None
    ) -> list[RouteConfig]:
        """List routes, optionally filtered by customer."""
        assert self._conn is not None
        if customer_id:
            rows = self._conn.execute(
                "SELECT * FROM routes WHERE customer_id = ? ORDER BY priority DESC",
                (customer_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM routes ORDER BY priority DESC"
            ).fetchall()
        return [self._row_to_config(r) for r in rows]

    async def update(self, route_id: str, data: RouteUpdate) -> Optional[RouteConfig]:
        """Partial update of a route config."""
        assert self._conn is not None
        existing = await self.get(route_id)
        if existing is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        updates = data.model_dump(exclude_none=True)

        if "name" in updates:
            existing.name = updates["name"]
        if "match" in updates:
            from app.router.schemas import MatchConfig
            existing.match = MatchConfig(**updates["match"])
        if "strategy" in updates:
            existing.strategy = updates["strategy"]
        if "rules" in updates:
            from app.router.schemas import RoutingRule
            existing.rules = [RoutingRule(**r) for r in updates["rules"]]
        if "fallback_chain" in updates:
            existing.fallback_chain = updates["fallback_chain"]
        if "enabled" in updates:
            existing.enabled = updates["enabled"]
        if "priority" in updates:
            existing.priority = updates["priority"]

        self._conn.execute(
            """UPDATE routes SET
               name = ?, match_config = ?, strategy = ?, rules = ?,
               fallback_chain = ?, enabled = ?, priority = ?, updated_at = ?
               WHERE route_id = ?""",
            (
                existing.name,
                existing.match.model_dump_json(),
                existing.strategy.value if hasattr(existing.strategy, "value") else existing.strategy,
                json.dumps([r.model_dump() for r in existing.rules]),
                json.dumps(existing.fallback_chain),
                int(existing.enabled),
                existing.priority,
                now,
                route_id,
            ),
        )
        self._conn.commit()
        await self.refresh_cache()
        return await self.get(route_id)

    async def delete(self, route_id: str) -> bool:
        """Delete a route. Returns True if it existed."""
        assert self._conn is not None
        cursor = self._conn.execute(
            "DELETE FROM routes WHERE route_id = ?", (route_id,)
        )
        self._conn.commit()
        if cursor.rowcount > 0:
            await self.refresh_cache()
            return True
        return False

    @staticmethod
    def _row_to_config(row: sqlite3.Row) -> RouteConfig:
        """Convert a database row to a RouteConfig."""
        from app.router.schemas import (
            ABTestConfig,
            CostBudget,
            MatchConfig,
            RoutingRule,
            RoutingStrategy,
        )

        match = MatchConfig(**json.loads(row["match_config"]))
        rules = [RoutingRule(**r) for r in json.loads(row["rules"])]
        fallback = json.loads(row["fallback_chain"])
        ab_test = ABTestConfig(**json.loads(row["ab_test"])) if row["ab_test"] else None
        cost_budget = CostBudget(**json.loads(row["cost_budget"])) if row["cost_budget"] else None

        return RouteConfig(
            route_id=row["route_id"],
            customer_id=row["customer_id"],
            name=row["name"],
            match=match,
            strategy=RoutingStrategy(row["strategy"]),
            rules=rules,
            fallback_chain=fallback,
            ab_test=ab_test,
            cost_budget=cost_budget,
            enabled=bool(row["enabled"]),
            priority=row["priority"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
