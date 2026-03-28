"""Workbook permission services."""

from __future__ import annotations

from app.storage.postgres_config import PostgresConfig
from app.storage.postgres_db import PostgresDatabase


class PermissionService:
    """Placeholder for owner/editor/viewer role workflows."""

    def can_edit(self, user_id: str, workbook_id: str) -> bool:  # noqa: ARG002
        raise NotImplementedError(
            "Permissions are scaffolded and will be implemented in later milestones."
        )


class PostgresPermissionService:
    """Permission checks for PostgreSQL-backed workbooks."""

    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.db = PostgresDatabase(config=config)

    def can_view(self, user_email: str, workbook_external_key: str) -> bool:
        """Return True if user has owner/editor/viewer permission for workbook."""
        role = self._fetch_role(user_email=user_email, workbook_external_key=workbook_external_key)
        return role in {"owner", "editor", "viewer"}

    def can_edit(self, user_email: str, workbook_external_key: str) -> bool:
        """Return True if user can edit workbook."""
        role = self._fetch_role(user_email=user_email, workbook_external_key=workbook_external_key)
        return role in {"owner", "editor"}

    def _fetch_role(self, user_email: str, workbook_external_key: str) -> str | None:
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT wp.role
                    FROM workbook_permissions wp
                    JOIN users u ON u.id = wp.user_id
                    JOIN workbooks w ON w.id = wp.workbook_id
                    WHERE u.email = %s AND w.external_key = %s
                    LIMIT 1
                    """,
                    (user_email, workbook_external_key),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return row["role"]
