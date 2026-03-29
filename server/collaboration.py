"""In-memory collaboration primitives for the FastAPI starter server.

This module intentionally implements only a realistic *starter* collaboration model:
- workbook session tracking
- user presence (sheet + cell/range focus)
- advisory cell/range locking scaffold
- fan-out event broadcasting to connected WebSocket clients

It does not implement full operational transforms / CRDT collaborative editing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import WebSocket


def utc_now() -> datetime:
    """Return a timezone-aware current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PresenceState:
    """Per-user visibility state for a workbook session."""

    user_id: str
    display_name: str
    session_id: str
    workbook_id: str
    current_sheet: str | None = None
    active_range: str | None = None
    last_seen: datetime = field(default_factory=utc_now)

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_seen"] = self.last_seen.isoformat()
        return payload


@dataclass(slots=True)
class LockState:
    """Advisory lock over a sheet cell/range."""

    workbook_id: str
    sheet_name: str
    range_ref: str
    holder_user_id: str
    holder_display_name: str
    acquired_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=lambda: utc_now() + timedelta(seconds=45))

    @property
    def lock_key(self) -> str:
        return f"{self.sheet_name}:{self.range_ref}"

    def refresh(self, ttl_seconds: int = 45) -> None:
        self.expires_at = utc_now() + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "workbook_id": self.workbook_id,
            "sheet_name": self.sheet_name,
            "range_ref": self.range_ref,
            "holder_user_id": self.holder_user_id,
            "holder_display_name": self.holder_display_name,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "lock_key": self.lock_key,
        }


class CollaborationHub:
    """Tracks sessions/presence and broadcasts events over WebSockets."""

    def __init__(self) -> None:
        self._presence_by_workbook: dict[str, dict[str, PresenceState]] = {}
        self._locks_by_workbook: dict[str, dict[str, LockState]] = {}
        self._ws_by_workbook: dict[str, set[WebSocket]] = {}

    def _purge_expired_locks(self, workbook_id: str) -> None:
        workbook_locks = self._locks_by_workbook.get(workbook_id, {})
        for lock_key in list(workbook_locks.keys()):
            if workbook_locks[lock_key].is_expired():
                del workbook_locks[lock_key]

    def register_socket(self, workbook_id: str, websocket: WebSocket) -> None:
        self._ws_by_workbook.setdefault(workbook_id, set()).add(websocket)

    def unregister_socket(self, workbook_id: str, websocket: WebSocket) -> None:
        sockets = self._ws_by_workbook.get(workbook_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._ws_by_workbook[workbook_id]

    async def publish(self, workbook_id: str, payload: dict[str, Any]) -> None:
        sockets = list(self._ws_by_workbook.get(workbook_id, set()))
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except RuntimeError:
                self.unregister_socket(workbook_id, socket)

    async def join(
        self,
        *,
        workbook_id: str,
        user_id: str,
        display_name: str,
        session_id: str,
        current_sheet: str | None,
        active_range: str | None,
    ) -> PresenceState:
        presence = PresenceState(
            user_id=user_id,
            display_name=display_name,
            session_id=session_id,
            workbook_id=workbook_id,
            current_sheet=current_sheet,
            active_range=active_range,
        )
        workbook_presence = self._presence_by_workbook.setdefault(workbook_id, {})
        workbook_presence[user_id] = presence
        await self.publish(workbook_id, {"event": "presence.joined", "presence": presence.to_public_dict()})
        return presence

    async def leave(self, workbook_id: str, user_id: str) -> None:
        workbook_presence = self._presence_by_workbook.get(workbook_id, {})
        prior = workbook_presence.pop(user_id, None)
        if prior is None:
            return
        await self.publish(workbook_id, {"event": "presence.left", "presence": prior.to_public_dict()})

    async def update_presence(
        self,
        *,
        workbook_id: str,
        user_id: str,
        current_sheet: str | None,
        active_range: str | None,
    ) -> PresenceState | None:
        workbook_presence = self._presence_by_workbook.get(workbook_id, {})
        state = workbook_presence.get(user_id)
        if state is None:
            return None
        state.current_sheet = current_sheet
        state.active_range = active_range
        state.last_seen = utc_now()
        await self.publish(workbook_id, {"event": "presence.updated", "presence": state.to_public_dict()})
        return state

    async def acquire_lock(
        self,
        *,
        workbook_id: str,
        user_id: str,
        display_name: str,
        sheet_name: str,
        range_ref: str,
    ) -> tuple[bool, LockState | None]:
        self._purge_expired_locks(workbook_id)
        workbook_locks = self._locks_by_workbook.setdefault(workbook_id, {})
        lock_key = f"{sheet_name}:{range_ref}"
        existing = workbook_locks.get(lock_key)

        if existing and existing.holder_user_id != user_id and not existing.is_expired():
            return False, existing

        lock_state = existing or LockState(
            workbook_id=workbook_id,
            sheet_name=sheet_name,
            range_ref=range_ref,
            holder_user_id=user_id,
            holder_display_name=display_name,
        )
        lock_state.holder_user_id = user_id
        lock_state.holder_display_name = display_name
        lock_state.refresh()
        workbook_locks[lock_key] = lock_state
        await self.publish(workbook_id, {"event": "lock.acquired", "lock": lock_state.to_public_dict()})
        return True, lock_state

    async def release_lock(self, *, workbook_id: str, user_id: str, sheet_name: str, range_ref: str) -> bool:
        workbook_locks = self._locks_by_workbook.get(workbook_id, {})
        lock_key = f"{sheet_name}:{range_ref}"
        existing = workbook_locks.get(lock_key)
        if existing is None or existing.holder_user_id != user_id:
            return False
        del workbook_locks[lock_key]
        await self.publish(
            workbook_id,
            {
                "event": "lock.released",
                "lock": {
                    "sheet_name": sheet_name,
                    "range_ref": range_ref,
                    "lock_key": lock_key,
                    "released_by": user_id,
                },
            },
        )
        return True

    def snapshot(self, workbook_id: str) -> dict[str, Any]:
        self._purge_expired_locks(workbook_id)
        presence = self._presence_by_workbook.get(workbook_id, {})
        locks = self._locks_by_workbook.get(workbook_id, {})
        return {
            "workbook_id": workbook_id,
            "participants": [p.to_public_dict() for p in presence.values()],
            "locks": [l.to_public_dict() for l in locks.values()],
            "capabilities": {
                "real_time_presence": True,
                "sheet_visibility": True,
                "cell_range_visibility": True,
                "advisory_locks": True,
                "collaborative_cell_edit_merging": False,
            },
        }
