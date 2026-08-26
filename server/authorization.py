"""Workbook-role resolution for collaboration endpoints."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Protocol

from app.permissions.service import PermissionService
from app.storage.json_storage import JsonWorkbookStorage, StorageValidationError
from app.storage.postgres_config import PostgresConfig
from app.storage.postgres_db import PostgresDatabase


class CollaborationAuthorizer(Protocol):
    def resolve_role(self, email: str, workbook_id: str) -> str | None: ...


class JsonWorkbookAuthorizer:
    """Resolve roles from server-visible JSON workbooks by filename stem."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir or os.getenv("JSON_DATA_DIR", "./data")).resolve()
        self.permissions = PermissionService()

    def resolve_role(self, email: str, workbook_id: str) -> str | None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", workbook_id):
            return None
        path = (self.data_dir / f"{workbook_id}.json").resolve()
        if path.parent != self.data_dir:
            return None
        try:
            workbook = JsonWorkbookStorage().load_workbook(str(path))
        except (OSError, StorageValidationError):
            return None
        return self.permissions.resolve_role(email, workbook)


class PostgresWorkbookAuthorizer:
    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.db = PostgresDatabase(config=config)

    def resolve_role(self, email: str, workbook_id: str) -> str | None:
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT wp.role
                    FROM workbook_permissions wp
                    JOIN users u ON u.id = wp.user_id
                    JOIN workbooks w ON w.id = wp.workbook_id
                    WHERE lower(u.email) = lower(%s) AND w.external_key = %s
                    """,
                    (email.strip(), workbook_id),
                )
                row = cur.fetchone()
        return str(row["role"]) if row else None


class StaticAuthorizer:
    """Deterministic authorizer for tests and embedded deployments."""

    def __init__(self, roles: dict[tuple[str, str], str] | None = None) -> None:
        self.roles = roles or {}

    def resolve_role(self, email: str, workbook_id: str) -> str | None:
        return self.roles.get((email.casefold(), workbook_id))


def create_authorizer() -> CollaborationAuthorizer:
    backend = os.getenv("STORAGE_BACKEND", "json").strip().lower()
    if backend == "postgres":
        return PostgresWorkbookAuthorizer()
    if backend == "json":
        return JsonWorkbookAuthorizer()
    raise ValueError("STORAGE_BACKEND must be either 'json' or 'postgres'.")
