"""Workbook permission service scaffold."""

from __future__ import annotations


class PermissionService:
    """Placeholder for owner/editor/viewer role workflows."""

    def can_edit(self, user_id: str, workbook_id: str) -> bool:  # noqa: ARG002
        raise NotImplementedError(
            "Permissions are scaffolded and will be implemented in later milestones."
        )
