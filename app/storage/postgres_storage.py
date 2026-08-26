"""PostgreSQL storage adapter implementation.

This adapter persists workbook JSON-equivalent structures into normalized PostgreSQL tables,
while exposing the same `load_workbook` / `save_workbook` API used by JSON storage.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.workbook import Workbook
from app.storage.postgres_config import PostgresConfig
from app.storage.postgres_db import PostgresDatabase


class PostgresStorageError(RuntimeError):
    """Raised for PostgreSQL persistence/load failures."""


class PostgresWorkbookStorage:
    """PostgreSQL-backed workbook persistence adapter."""

    def __init__(
        self,
        config: PostgresConfig | None = None,
        database: PostgresDatabase | None = None,
    ) -> None:
        self.db = database or PostgresDatabase(config=config)

    def list_workbooks(self, user_email: str | None = None) -> list[dict[str, Any]]:
        """List workbook references, optionally restricted to a user's access."""
        query = """
            SELECT DISTINCT w.external_key, w.name, w.updated_at
            FROM workbooks w
        """
        params: tuple[Any, ...] = ()
        if user_email:
            query += """
                JOIN workbook_permissions wp ON wp.workbook_id = w.id
                JOIN users u ON u.id = wp.user_id
                WHERE lower(u.email) = lower(%s)
            """
            params = (user_email.strip(),)
        query += " ORDER BY w.updated_at DESC, w.name ASC"
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return list(cur.fetchall())

    def load_workbook_for_user(self, path: str, user_email: str) -> Workbook:
        """Load only when the user has owner, editor, or viewer access."""
        return self._load_workbook(path=path, user_email=user_email)

    def load_workbook(self, path: str) -> Workbook:
        """Load a workbook identified by `path` as external key.

        The `path` argument is treated as a stable external identifier when using
        PostgreSQL storage (for example: `workbook://sales-q1` or `sales_q1`).
        """

        return self._load_workbook(path=path, user_email=None)

    def _load_workbook(self, path: str, user_email: str | None) -> Workbook:
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                permission_clause = ""
                params: tuple[Any, ...] = (path,)
                if user_email:
                    permission_clause = """
                        AND EXISTS (
                            SELECT 1 FROM workbook_permissions wp
                            JOIN users u ON u.id = wp.user_id
                            WHERE wp.workbook_id = workbooks.id
                              AND lower(u.email) = lower(%s)
                        )
                    """
                    params = (path, user_email.strip())
                cur.execute(
                    f"""
                    SELECT id, name, active_sheet_index, metadata
                    FROM workbooks
                    WHERE external_key = %s
                    {permission_clause}
                    """,
                    params,
                )
                workbook_row = cur.fetchone()
                if workbook_row is None:
                    raise PostgresStorageError(f"Workbook not found or access denied: {path}")

                cur.execute(
                    """
                    SELECT id, name, position, metadata
                    FROM sheets
                    WHERE workbook_id = %s
                    ORDER BY position ASC
                    """,
                    (workbook_row["id"],),
                )
                sheet_rows = cur.fetchall()

                sheets: list[dict[str, Any]] = []
                for sheet_row in sheet_rows:
                    cur.execute(
                        """
                        SELECT address, value_json, formula, formatting
                        FROM cells
                        WHERE sheet_id = %s
                        ORDER BY address ASC
                        """,
                        (sheet_row["id"],),
                    )
                    cell_rows = cur.fetchall()
                    cells: dict[str, dict[str, Any]] = {}
                    for cell_row in cell_rows:
                        value_payload = cell_row["value_json"]
                        if isinstance(value_payload, str):
                            value_payload = json.loads(value_payload)

                        formatting_payload = cell_row["formatting"]
                        if isinstance(formatting_payload, str):
                            formatting_payload = json.loads(formatting_payload)

                        cells[cell_row["address"]] = {
                            "value": value_payload,
                            "formula": cell_row["formula"],
                            "formatting": formatting_payload or {},
                        }

                    sheets.append(
                        {
                            "name": sheet_row["name"],
                            "metadata": _json_object(sheet_row["metadata"]),
                            "cells": cells,
                        }
                    )

                permissions = self._load_permissions(cur, workbook_row["id"])

        payload: dict[str, Any] = {
            "name": workbook_row["name"],
            "active_sheet_index": workbook_row["active_sheet_index"] or 0,
            "metadata": _json_object(workbook_row["metadata"]),
            "permissions": permissions,
            "sheets": sheets,
        }
        return Workbook.from_dict(payload)

    def save_workbook(self, path: str, workbook: Workbook) -> None:
        """Save workbook content to PostgreSQL using upsert semantics."""

        self._save_workbook(path=path, workbook=workbook, actor_email=None)

    def save_workbook_for_user(self, path: str, workbook: Workbook, user_email: str) -> None:
        """Save an existing workbook only when the user has edit permission.

        A new workbook may be created only when its model names the actor as owner.
        """
        self._save_workbook(path=path, workbook=workbook, actor_email=user_email)

    def _save_workbook(
        self,
        path: str,
        workbook: Workbook,
        actor_email: str | None,
    ) -> None:
        if not path.strip():
            raise PostgresStorageError("PostgreSQL workbook key cannot be empty.")

        payload = workbook.to_dict()

        with self.db.transaction() as conn:
            with conn.cursor() as cur:
                actor_role: str | None = None
                if actor_email:
                    actor_role = self._authorize_save(
                        cur, path, actor_email, payload.get("permissions", {})
                    )
                cur.execute(
                    """
                    INSERT INTO workbooks (external_key, name, active_sheet_index, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (external_key)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        active_sheet_index = EXCLUDED.active_sheet_index,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        path,
                        payload["name"],
                        payload["active_sheet_index"],
                        json.dumps(payload.get("metadata", {})),
                    ),
                )
                workbook_id = cur.fetchone()["id"]

                cur.execute("DELETE FROM sheets WHERE workbook_id = %s", (workbook_id,))

                for position, sheet_payload in enumerate(payload.get("sheets", [])):
                    cur.execute(
                        """
                        INSERT INTO sheets (workbook_id, position, name, metadata)
                        VALUES (%s, %s, %s, %s::jsonb)
                        RETURNING id
                        """,
                        (
                            workbook_id,
                            position,
                            sheet_payload.get("name", f"Sheet{position + 1}"),
                            json.dumps(sheet_payload.get("metadata", {})),
                        ),
                    )
                    sheet_id = cur.fetchone()["id"]

                    for address, cell_payload in (sheet_payload.get("cells", {}) or {}).items():
                        cur.execute(
                            """
                            INSERT INTO cells (sheet_id, address, value_json, formula, formatting)
                            VALUES (%s, %s, %s::jsonb, %s, %s::jsonb)
                            """,
                            (
                                sheet_id,
                                address.upper(),
                                json.dumps(cell_payload.get("value")),
                                cell_payload.get("formula"),
                                json.dumps(cell_payload.get("formatting", {})),
                            ),
                        )

                # Editors may update workbook content but cannot escalate roles by
                # modifying the permissions embedded in a client payload.
                if actor_role != "editor":
                    self._sync_permissions(cur, workbook_id, payload.get("permissions", {}))
                    owner = payload.get("permissions", {}).get("owner")
                    owner_id = (
                        self._ensure_user(cur, owner)
                        if isinstance(owner, str) and owner.strip()
                        else None
                    )
                    cur.execute(
                        "UPDATE workbooks SET owner_user_id = %s WHERE id = %s",
                        (owner_id, workbook_id),
                    )

    def delete_workbook(self, path: str, actor_email: str) -> None:
        """Delete a workbook only when the actor is its owner."""
        with self.db.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM workbooks w
                    WHERE w.external_key = %s
                      AND EXISTS (
                        SELECT 1 FROM workbook_permissions wp
                        JOIN users u ON u.id = wp.user_id
                        WHERE wp.workbook_id = w.id
                          AND lower(u.email) = lower(%s)
                          AND wp.role = 'owner'
                      )
                    RETURNING w.id
                    """,
                    (path, actor_email.strip()),
                )
                if cur.fetchone() is None:
                    raise PostgresStorageError("Workbook not found or owner access required.")

    def _authorize_save(
        self,
        cur: Any,
        path: str,
        actor_email: str,
        permissions: dict[str, Any],
    ) -> str:
        cur.execute("SELECT id FROM workbooks WHERE external_key = %s", (path,))
        existing = cur.fetchone()
        if existing is None:
            owner = permissions.get("owner")
            if not isinstance(owner, str) or owner.strip().casefold() != actor_email.strip().casefold():
                raise PostgresStorageError("New PostgreSQL workbooks must assign the actor as owner.")
            return "owner"
        cur.execute(
            """
            SELECT wp.role
            FROM workbook_permissions wp
            JOIN users u ON u.id = wp.user_id
            WHERE wp.workbook_id = %s AND lower(u.email) = lower(%s)
            """,
            (existing["id"], actor_email.strip()),
        )
        access = cur.fetchone()
        if access is None or access["role"] not in {"owner", "editor"}:
            raise PostgresStorageError("Editor or owner access is required to save this workbook.")
        return access["role"]

    def _load_permissions(self, cur: Any, workbook_id: str) -> dict[str, Any]:
        cur.execute(
            """
            SELECT u.email, wp.role
            FROM workbook_permissions wp
            JOIN users u ON u.id = wp.user_id
            WHERE wp.workbook_id = %s
            ORDER BY u.email ASC
            """,
            (workbook_id,),
        )
        entries = cur.fetchall()
        owner_email = next((entry["email"] for entry in entries if entry["role"] == "owner"), None)
        shared_with = [
            {"user": entry["email"], "role": entry["role"]}
            for entry in entries
            if entry["role"] != "owner"
        ]
        return {"owner": owner_email, "shared_with": shared_with}

    def _sync_permissions(self, cur: Any, workbook_id: str, permissions: dict[str, Any]) -> None:
        cur.execute("DELETE FROM workbook_permissions WHERE workbook_id = %s", (workbook_id,))

        owner = permissions.get("owner")
        if isinstance(owner, str) and owner.strip():
            owner_id = self._ensure_user(cur, owner.strip())
            cur.execute(
                """
                INSERT INTO workbook_permissions (workbook_id, user_id, role)
                VALUES (%s, %s, 'owner')
                ON CONFLICT (workbook_id, user_id)
                DO UPDATE SET role = EXCLUDED.role
                """,
                (workbook_id, owner_id),
            )

        for entry in permissions.get("shared_with", []):
            if not isinstance(entry, dict):
                continue
            email = entry.get("user")
            if not isinstance(email, str) or not email.strip():
                continue
            role = str(entry.get("role") or "viewer").lower()
            if role not in {"viewer", "editor"}:
                role = "viewer"

            user_id = self._ensure_user(cur, email.strip())
            cur.execute(
                """
                INSERT INTO workbook_permissions (workbook_id, user_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (workbook_id, user_id)
                DO UPDATE SET role = EXCLUDED.role
                """,
                (workbook_id, user_id, role),
            )

    def _ensure_user(self, cur: Any, email: str) -> str:
        email = email.strip().casefold()
        cur.execute(
            """
            INSERT INTO users (email)
            VALUES (%s)
            ON CONFLICT (email)
            DO UPDATE SET email = EXCLUDED.email
            RETURNING id
            """,
            (email,),
        )
        return cur.fetchone()["id"]


def _json_object(value: Any) -> dict[str, Any]:
    """Normalize JSONB values from both real and lightweight test drivers."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}
