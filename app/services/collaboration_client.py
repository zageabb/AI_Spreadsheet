"""Desktop-client collaboration API contract scaffolding.

This module keeps collaboration transport concerns out of UI widgets and can be
wired to HTTP/WebSocket clients incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class CollaborationIdentity:
    """Authenticated identity details needed by collaboration service."""

    user_id: str
    display_name: str


@dataclass(slots=True)
class PresencePayload:
    """Current workbook visibility state for a user."""

    current_sheet: str | None = None
    active_range: str | None = None


class CollaborationClient(Protocol):
    """Transport-neutral collaboration client interface for desktop integration."""

    def join_workbook(self, workbook_id: str, identity: CollaborationIdentity, presence: PresencePayload) -> str:
        """Join a workbook session and return the collaboration session id."""

    def update_presence(self, workbook_id: str, identity: CollaborationIdentity, presence: PresencePayload) -> None:
        """Update current sheet and cell/range focus visibility."""

    def leave_workbook(self, workbook_id: str, identity: CollaborationIdentity) -> None:
        """Leave workbook collaboration session."""

    def acquire_advisory_lock(self, workbook_id: str, identity: CollaborationIdentity, sheet: str, range_ref: str) -> bool:
        """Attempt to acquire an advisory lock for a range."""

    def release_advisory_lock(self, workbook_id: str, identity: CollaborationIdentity, sheet: str, range_ref: str) -> None:
        """Release an advisory lock held by this user."""
