"""Permissions module exports."""

from app.permissions.service import PermissionService, PostgresPermissionService

__all__ = ["PermissionService", "PostgresPermissionService"]
