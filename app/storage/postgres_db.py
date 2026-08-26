"""Low-level PostgreSQL access helpers.

This module intentionally isolates DB access from UI and workbook business logic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.storage.postgres_config import PostgresConfig

if TYPE_CHECKING:
    from psycopg import Connection


class PostgresDatabase:
    """Small wrapper around psycopg connection lifecycle."""

    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.config = config or PostgresConfig.from_env()

    @contextmanager
    def connection(self) -> Iterator["Connection[Any]"]:
        """Yield a connection with dict row mapping enabled."""
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "psycopg is required for PostgreSQL backend. Install requirements.txt dependencies."
            ) from exc

        with connect(**self.config.connection_kwargs(), row_factory=dict_row) as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Iterator["Connection[Any]"]:
        """Yield a connection and atomically commit or roll back the operation."""
        with self.connection() as conn:
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    def check_connection(self) -> bool:
        """Run a lightweight readiness check used by setup and diagnostics."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ready")
                row = cur.fetchone()
        return bool(row and row["ready"] == 1)

    def run_schema_file(self, schema_path: str | Path) -> None:
        """Initialize/refresh database objects from a SQL file."""
        sql = Path(schema_path).read_text(encoding="utf-8")
        with self.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
