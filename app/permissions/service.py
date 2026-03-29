"""Workbook permission services and reusable access-control workflows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from app.models.workbook import Workbook
from app.services.email_service import EmailNotificationService
from app.storage.postgres_config import PostgresConfig
from app.storage.postgres_db import PostgresDatabase


Role = Literal["owner", "editor", "viewer"]
_ALLOWED_ROLES: set[str] = {"owner", "editor", "viewer"}


@dataclass(slots=True)
class AccessEntry:
    """Resolved workbook access entry."""

    user: str
    role: Role


class PermissionService:
    """Reusable permission logic for JSON and shared business workflows."""

    def create_workbook_with_owner(self, workbook_name: str, owner_email: str) -> Workbook:
        """Create a workbook with owner role assigned."""
        workbook = Workbook(name=workbook_name)
        workbook.permissions = self.assign_owner(workbook.permissions, owner_email)
        return workbook

    def assign_owner(self, permissions: dict[str, Any], owner_email: str) -> dict[str, Any]:
        """Assign owner for workbook permissions."""
        owner = _normalize_email(owner_email)
        updated = self._normalized_permissions(permissions)
        updated["owner"] = owner
        updated["shared_with"] = [entry for entry in updated["shared_with"] if entry["user"] != owner]
        return updated

    def transfer_ownership(
        self,
        permissions: dict[str, Any],
        actor_email: str,
        new_owner_email: str,
    ) -> dict[str, Any]:
        """Transfer workbook ownership from current owner to a new owner."""
        self._require_owner(actor_email=actor_email, permissions=permissions)
        return self.assign_owner(permissions=permissions, owner_email=new_owner_email)

    def invite_user_as_owner(
        self,
        permissions: dict[str, Any],
        actor_email: str,
        user_email: str,
        role: Role = "viewer",
    ) -> dict[str, Any]:
        """Invite user with role, requiring owner privileges for actor."""
        self._require_owner(actor_email=actor_email, permissions=permissions)
        return self.invite_user(permissions=permissions, user_email=user_email, role=role)

    def invite_user(self, permissions: dict[str, Any], user_email: str, role: Role = "viewer") -> dict[str, Any]:
        """Invite user to workbook with default viewer role."""
        return self.grant_access(permissions=permissions, user_email=user_email, role=role)

    def grant_editor_access_as_owner(
        self,
        permissions: dict[str, Any],
        actor_email: str,
        user_email: str,
    ) -> dict[str, Any]:
        """Grant editor role when actor is workbook owner."""
        self._require_owner(actor_email=actor_email, permissions=permissions)
        return self.grant_editor_access(permissions=permissions, user_email=user_email)

    def grant_viewer_access_as_owner(
        self,
        permissions: dict[str, Any],
        actor_email: str,
        user_email: str,
    ) -> dict[str, Any]:
        """Grant viewer role when actor is workbook owner."""
        self._require_owner(actor_email=actor_email, permissions=permissions)
        return self.grant_viewer_access(permissions=permissions, user_email=user_email)

    def revoke_access_as_owner(
        self,
        permissions: dict[str, Any],
        actor_email: str,
        user_email: str,
    ) -> dict[str, Any]:
        """Revoke user role when actor is workbook owner."""
        self._require_owner(actor_email=actor_email, permissions=permissions)
        return self.revoke_access(permissions=permissions, user_email=user_email)

    def grant_editor_access(self, permissions: dict[str, Any], user_email: str) -> dict[str, Any]:
        """Grant editor role to user."""
        return self.grant_access(permissions=permissions, user_email=user_email, role="editor")

    def grant_viewer_access(self, permissions: dict[str, Any], user_email: str) -> dict[str, Any]:
        """Grant viewer role to user."""
        return self.grant_access(permissions=permissions, user_email=user_email, role="viewer")

    def grant_access(self, permissions: dict[str, Any], user_email: str, role: Role) -> dict[str, Any]:
        """Grant or update non-owner role for a user."""
        normalized_role = _normalize_role(role)
        if normalized_role == "owner":
            raise ValueError("Use assign_owner to set owner role.")

        user = _normalize_email(user_email)
        updated = self._normalized_permissions(permissions)

        if updated["owner"] == user:
            raise ValueError("Owner already has owner access.")

        shared_entries = [entry for entry in updated["shared_with"] if entry["user"] != user]
        shared_entries.append({"user": user, "role": normalized_role})
        shared_entries.sort(key=lambda entry: entry["user"])

        updated["shared_with"] = shared_entries
        return updated

    def revoke_access(self, permissions: dict[str, Any], user_email: str) -> dict[str, Any]:
        """Revoke non-owner access for a user."""
        user = _normalize_email(user_email)
        updated = self._normalized_permissions(permissions)

        if updated["owner"] == user:
            raise ValueError("Owner access cannot be revoked; assign a new owner first.")

        updated["shared_with"] = [entry for entry in updated["shared_with"] if entry["user"] != user]
        return updated

    def can_view(self, user_email: str, workbook: Workbook | dict[str, Any]) -> bool:
        """Check if user can view workbook."""
        role = self.resolve_role(user_email=user_email, workbook=workbook)
        return role in {"owner", "editor", "viewer"}

    def can_edit(self, user_email: str, workbook: Workbook | dict[str, Any]) -> bool:
        """Check if user can edit workbook."""
        role = self.resolve_role(user_email=user_email, workbook=workbook)
        return role in {"owner", "editor"}

    def resolve_role(self, user_email: str, workbook: Workbook | dict[str, Any]) -> Role | None:
        """Resolve effective role for a user in a workbook."""
        user = _normalize_email(user_email)
        permissions = self._normalized_permissions(_extract_permissions(workbook))

        if permissions["owner"] == user:
            return "owner"

        for entry in permissions["shared_with"]:
            if entry["user"] == user:
                return entry["role"]

        return None

    def _require_owner(self, actor_email: str, permissions: dict[str, Any]) -> None:
        actor = _normalize_email(actor_email)
        normalized_permissions = self._normalized_permissions(permissions)
        if normalized_permissions.get("owner") != actor:
            raise PermissionError("Only workbook owners can modify sharing permissions.")

    def _normalized_permissions(self, permissions: dict[str, Any]) -> dict[str, Any]:
        cloned = deepcopy(permissions) if isinstance(permissions, dict) else {}
        owner = cloned.get("owner")

        normalized_owner = _normalize_email(owner) if isinstance(owner, str) and owner.strip() else None
        shared_with = cloned.get("shared_with", [])
        normalized_shared: list[dict[str, str]] = []
        if isinstance(shared_with, list):
            for entry in shared_with:
                if not isinstance(entry, dict):
                    continue
                user = entry.get("user")
                if not isinstance(user, str) or not user.strip():
                    continue
                normalized_user = _normalize_email(user)
                if normalized_user == normalized_owner:
                    continue
                normalized_shared.append(
                    {
                        "user": normalized_user,
                        "role": _normalize_role(entry.get("role", "viewer")),
                    }
                )

        dedup: dict[str, str] = {}
        for entry in normalized_shared:
            dedup[entry["user"]] = entry["role"]

        return {
            "owner": normalized_owner,
            "shared_with": [
                {"user": user, "role": role}
                for user, role in sorted(dedup.items(), key=lambda item: item[0])
            ],
        }


class SharingWorkflowService:
    """Workflow orchestration for permission updates + email notifications."""

    def __init__(
        self,
        permission_service: PermissionService | None = None,
        email_service: EmailNotificationService | None = None,
    ) -> None:
        self.permission_service = permission_service or PermissionService()
        self.email_service = email_service or EmailNotificationService()

    def invite_user(
        self,
        workbook: Workbook,
        actor_email: str,
        target_email: str,
        role: Role = "viewer",
        workbook_link: str = "",
    ) -> Workbook:
        workbook.permissions = self.permission_service.invite_user_as_owner(
            permissions=workbook.permissions,
            actor_email=actor_email,
            user_email=target_email,
            role=role,
        )
        self.email_service.send_workbook_invitation(
            recipient_email=target_email,
            workbook_name=workbook.name,
            inviter_email=actor_email,
            role=role,
            workbook_link=workbook_link,
        )
        return workbook

    def grant_access(
        self,
        workbook: Workbook,
        actor_email: str,
        target_email: str,
        role: Role,
        workbook_link: str = "",
    ) -> Workbook:
        workbook.permissions = self.permission_service.grant_access(
            permissions=workbook.permissions,
            user_email=target_email,
            role=role,
        )
        self.email_service.send_access_granted(
            recipient_email=target_email,
            workbook_name=workbook.name,
            granted_by_email=actor_email,
            role=role,
            workbook_link=workbook_link,
        )
        return workbook

    def revoke_access(self, workbook: Workbook, actor_email: str, target_email: str) -> Workbook:
        workbook.permissions = self.permission_service.revoke_access_as_owner(
            permissions=workbook.permissions,
            actor_email=actor_email,
            user_email=target_email,
        )
        self.email_service.send_access_removed(
            recipient_email=target_email,
            workbook_name=workbook.name,
            removed_by_email=actor_email,
        )
        return workbook


class PostgresPermissionService:
    """Permission checks and grants for PostgreSQL-backed workbooks."""

    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.db = PostgresDatabase(config=config)

    def can_view(self, user_email: str, workbook_external_key: str) -> bool:
        role = self._fetch_role(user_email=user_email, workbook_external_key=workbook_external_key)
        return role in {"owner", "editor", "viewer"}

    def can_edit(self, user_email: str, workbook_external_key: str) -> bool:
        role = self._fetch_role(user_email=user_email, workbook_external_key=workbook_external_key)
        return role in {"owner", "editor"}

    def grant_access(
        self,
        actor_email: str,
        target_email: str,
        workbook_external_key: str,
        role: Role,
    ) -> None:
        """Grant viewer/editor role when actor is workbook owner."""
        actor_role = self._fetch_role(actor_email, workbook_external_key)
        if actor_role != "owner":
            raise PermissionError("Only workbook owners can grant access.")

        normalized_role = _normalize_role(role)
        if normalized_role == "owner":
            raise ValueError("Use owner assignment workflow for owner role changes.")

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                workbook_id = self._fetch_workbook_id(cur, workbook_external_key)
                actor_id = self._fetch_user_id(cur, _normalize_email(actor_email))
                target_id = self._ensure_user(cur, _normalize_email(target_email))

                cur.execute(
                    """
                    INSERT INTO workbook_permissions (workbook_id, user_id, role, granted_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (workbook_id, user_id)
                    DO UPDATE SET role = EXCLUDED.role, granted_by = EXCLUDED.granted_by
                    """,
                    (workbook_id, target_id, normalized_role, actor_id),
                )
            conn.commit()

    def revoke_access(self, actor_email: str, target_email: str, workbook_external_key: str) -> None:
        """Revoke non-owner access when actor is workbook owner."""
        actor_role = self._fetch_role(actor_email, workbook_external_key)
        if actor_role != "owner":
            raise PermissionError("Only workbook owners can revoke access.")

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                workbook_id = self._fetch_workbook_id(cur, workbook_external_key)
                target_id = self._fetch_user_id(cur, _normalize_email(target_email))
                if target_id is None:
                    return

                cur.execute(
                    "DELETE FROM workbook_permissions WHERE workbook_id = %s AND user_id = %s AND role <> 'owner'",
                    (workbook_id, target_id),
                )
            conn.commit()

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
                    (_normalize_email(user_email), workbook_external_key),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return row["role"]

    def _fetch_workbook_id(self, cur: Any, workbook_external_key: str) -> str:
        cur.execute("SELECT id FROM workbooks WHERE external_key = %s", (workbook_external_key,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Workbook not found: {workbook_external_key}")
        return row["id"]

    def _fetch_user_id(self, cur: Any, email: str) -> str | None:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        return row["id"] if row else None

    def _ensure_user(self, cur: Any, email: str) -> str:
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


def _extract_permissions(workbook: Workbook | dict[str, Any]) -> dict[str, Any]:
    if isinstance(workbook, Workbook):
        return workbook.permissions
    if isinstance(workbook, dict):
        return workbook.get("permissions", {}) if isinstance(workbook.get("permissions", {}), dict) else {}
    return {}


def _normalize_email(email: str) -> str:
    normalized = email.lower().strip()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("A valid email address is required.")
    return normalized


def _normalize_role(role: str) -> Role:
    normalized = str(role).lower().strip()
    if normalized not in _ALLOWED_ROLES:
        raise ValueError("Role must be one of: owner, editor, viewer.")
    return normalized  # type: ignore[return-value]
