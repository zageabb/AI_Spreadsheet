"""Authenticated session, presence, lock and revision primitives.

This is revisioned last-writer coordination, not CRDT/OT merging. Accepted cell
events are held in memory and broadcast; durable saves remain client-owned.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from fastapi import WebSocket

from app.core.coordinates import CellAddress


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PresenceState:
    user_id: str
    email: str
    display_name: str
    session_id: str
    workbook_id: str
    role: str
    current_sheet: str | None = None
    active_range: str | None = None
    last_seen: datetime = field(default_factory=utc_now)

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_seen"] = self.last_seen.isoformat()
        return payload


@dataclass(slots=True)
class LockState:
    workbook_id: str
    sheet_name: str
    range_ref: str
    holder_user_id: str
    holder_session_id: str
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
        payload = asdict(self)
        payload["acquired_at"] = self.acquired_at.isoformat()
        payload["expires_at"] = self.expires_at.isoformat()
        payload["lock_key"] = self.lock_key
        return payload


@dataclass(slots=True)
class CellChange:
    operation_id: str
    workbook_id: str
    sheet_name: str
    address: str
    value: Any
    formula: str | None
    user_id: str
    session_id: str
    revision: int
    changed_at: datetime = field(default_factory=utc_now)

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["changed_at"] = self.changed_at.isoformat()
        return payload


class CollaborationHub:
    """In-memory coordination hub with deterministic workbook revisions."""

    def __init__(self, presence_ttl_seconds: int = 90, history_limit: int = 200) -> None:
        self.presence_ttl_seconds = presence_ttl_seconds
        self.history_limit = history_limit
        self._presence: dict[str, dict[str, PresenceState]] = {}
        self._locks: dict[str, dict[str, LockState]] = {}
        self._sockets: dict[str, set[WebSocket]] = {}
        self._revisions: dict[str, int] = {}
        self._history: dict[str, list[CellChange]] = {}
        self._operations: dict[str, dict[str, CellChange]] = {}

    def register_socket(self, workbook_id: str, websocket: WebSocket) -> None:
        self._sockets.setdefault(workbook_id, set()).add(websocket)

    def unregister_socket(self, workbook_id: str, websocket: WebSocket) -> None:
        sockets = self._sockets.get(workbook_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                self._sockets.pop(workbook_id, None)

    async def publish(self, workbook_id: str, payload: dict[str, Any]) -> None:
        for socket in list(self._sockets.get(workbook_id, set())):
            try:
                await socket.send_json(payload)
            except (RuntimeError, OSError):
                self.unregister_socket(workbook_id, socket)

    async def join(self, *, workbook_id: str, user_id: str, email: str,
                   display_name: str, session_id: str, role: str,
                   current_sheet: str | None, active_range: str | None) -> PresenceState:
        state = PresenceState(user_id, email, display_name, session_id, workbook_id, role,
                              current_sheet, _normalized_range(active_range))
        self._presence.setdefault(workbook_id, {})[session_id] = state
        await self.publish(workbook_id, {"event": "presence.joined", "presence": state.to_public_dict()})
        return state

    async def leave(self, workbook_id: str, session_id: str, user_id: str) -> bool:
        state = self._presence.get(workbook_id, {}).get(session_id)
        if state is None or state.user_id != user_id:
            return False
        self._presence[workbook_id].pop(session_id, None)
        for key, lock in list(self._locks.get(workbook_id, {}).items()):
            if lock.holder_session_id == session_id:
                self._locks[workbook_id].pop(key, None)
        await self.publish(workbook_id, {"event": "presence.left", "presence": state.to_public_dict()})
        return True

    async def update_presence(self, *, workbook_id: str, session_id: str, user_id: str,
                              current_sheet: str | None, active_range: str | None) -> PresenceState | None:
        state = self._presence.get(workbook_id, {}).get(session_id)
        if state is None or state.user_id != user_id:
            return None
        state.current_sheet = current_sheet
        state.active_range = _normalized_range(active_range)
        state.last_seen = utc_now()
        await self.publish(workbook_id, {"event": "presence.updated", "presence": state.to_public_dict()})
        return state

    async def acquire_lock(self, *, workbook_id: str, user_id: str, session_id: str,
                           display_name: str, sheet_name: str,
                           range_ref: str) -> tuple[bool, LockState | None]:
        normalized = _normalized_range(range_ref)
        if not sheet_name.strip() or normalized is None:
            raise ValueError("A valid sheet and cell/range are required.")
        self._purge(workbook_id)
        locks = self._locks.setdefault(workbook_id, {})
        for existing in locks.values():
            if (existing.sheet_name.casefold() == sheet_name.casefold()
                    and existing.holder_session_id != session_id
                    and ranges_overlap(existing.range_ref, normalized)):
                return False, existing
        key = f"{sheet_name}:{normalized}"
        state = locks.get(key) or LockState(workbook_id, sheet_name, normalized, user_id,
                                            session_id, display_name)
        state.holder_user_id = user_id
        state.holder_session_id = session_id
        state.holder_display_name = display_name
        state.refresh()
        locks[key] = state
        await self.publish(workbook_id, {"event": "lock.acquired", "lock": state.to_public_dict()})
        return True, state

    async def release_lock(self, *, workbook_id: str, user_id: str, session_id: str,
                           sheet_name: str, range_ref: str) -> bool:
        normalized = _normalized_range(range_ref)
        key = f"{sheet_name}:{normalized}"
        existing = self._locks.get(workbook_id, {}).get(key)
        if (existing is None or existing.holder_user_id != user_id
                or existing.holder_session_id != session_id):
            return False
        self._locks[workbook_id].pop(key, None)
        await self.publish(workbook_id, {"event": "lock.released", "lock": existing.to_public_dict()})
        return True

    async def apply_cell_change(self, *, workbook_id: str, operation_id: str,
                                base_revision: int, sheet_name: str, address: str,
                                value: Any, formula: str | None, user_id: str,
                                session_id: str) -> tuple[bool, CellChange | None, dict[str, Any] | None]:
        normalized_address = _normalized_range(address)
        if not operation_id.strip() or normalized_address is None or ":" in normalized_address:
            raise ValueError("A valid operation id and single-cell address are required.")
        prior = self._operations.get(workbook_id, {}).get(operation_id)
        if prior:
            return True, prior, None
        current = self._revisions.get(workbook_id, 0)
        if base_revision != current:
            recent = [change.to_public_dict() for change in self._history.get(workbook_id, [])
                      if change.revision > base_revision]
            return False, None, {"current_revision": current, "changes": recent[-50:]}
        change = CellChange(operation_id, workbook_id, sheet_name, normalized_address,
                            value, formula, user_id, session_id, current + 1)
        self._revisions[workbook_id] = change.revision
        history = self._history.setdefault(workbook_id, [])
        history.append(change)
        del history[:-self.history_limit]
        operations = self._operations.setdefault(workbook_id, {})
        operations[operation_id] = change
        if len(operations) > self.history_limit * 2:
            retained = {item.operation_id for item in history}
            self._operations[workbook_id] = {key: item for key, item in operations.items()
                                                if key in retained}
        await self.publish(workbook_id, {"event": "cell.updated", "change": change.to_public_dict()})
        return True, change, None

    async def expire_stale_sessions(self, workbook_id: str) -> list[str]:
        """Expire abandoned sessions and broadcast their departure."""
        cutoff = utc_now() - timedelta(seconds=self.presence_ttl_seconds)
        expired = [
            (session_id, state.user_id)
            for session_id, state in self._presence.get(workbook_id, {}).items()
            if state.last_seen < cutoff
        ]
        for session_id, user_id in expired:
            await self.leave(workbook_id, session_id, user_id)
        return [session_id for session_id, _user_id in expired]

    def session(self, workbook_id: str, session_id: str, user_id: str) -> PresenceState | None:
        self._purge(workbook_id)
        state = self._presence.get(workbook_id, {}).get(session_id)
        return state if state and state.user_id == user_id else None

    def conflicting_lock(self, workbook_id: str, sheet_name: str, range_ref: str,
                         session_id: str) -> LockState | None:
        self._purge(workbook_id)
        normalized = _normalized_range(range_ref)
        if normalized is None:
            return None
        for lock in self._locks.get(workbook_id, {}).values():
            if (lock.holder_session_id != session_id
                    and lock.sheet_name.casefold() == sheet_name.casefold()
                    and ranges_overlap(lock.range_ref, normalized)):
                return lock
        return None

    def snapshot(self, workbook_id: str) -> dict[str, Any]:
        self._purge(workbook_id)
        return {
            "workbook_id": workbook_id,
            "revision": self._revisions.get(workbook_id, 0),
            "participants": [item.to_public_dict() for item in self._presence.get(workbook_id, {}).values()],
            "locks": [item.to_public_dict() for item in self._locks.get(workbook_id, {}).values()],
            "recent_changes": [item.to_public_dict() for item in self._history.get(workbook_id, [])[-50:]],
            "capabilities": {
                "authenticated_presence": True,
                "cell_event_broadcast": True,
                "revision_conflicts": True,
                "overlapping_advisory_locks": True,
                "durable_server_side_cell_persistence": False,
                "crdt_or_operational_transform_merging": False,
            },
        }

    def _purge(self, workbook_id: str) -> None:
        cutoff = utc_now() - timedelta(seconds=self.presence_ttl_seconds)
        for session_id, state in list(self._presence.get(workbook_id, {}).items()):
            if state.last_seen < cutoff:
                self._presence[workbook_id].pop(session_id, None)
        for key, lock in list(self._locks.get(workbook_id, {}).items()):
            if lock.is_expired() or lock.holder_session_id not in self._presence.get(workbook_id, {}):
                self._locks[workbook_id].pop(key, None)


_RANGE_PATTERN = re.compile(r"^([A-Za-z]+[1-9][0-9]*)(?::([A-Za-z]+[1-9][0-9]*))?$")


def _normalized_range(value: str | None) -> str | None:
    if value is None:
        return None
    match = _RANGE_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    start = match.group(1).upper()
    end = match.group(2).upper() if match.group(2) else None
    return f"{start}:{end}" if end else start


def _bounds(range_ref: str) -> tuple[int, int, int, int]:
    start_text, _, end_text = range_ref.partition(":")
    start = CellAddress.parse(start_text)
    end = CellAddress.parse(end_text or start_text)
    return (min(start.row, end.row), max(start.row, end.row),
            min(start.column, end.column), max(start.column, end.column))


def ranges_overlap(left: str, right: str) -> bool:
    l_top, l_bottom, l_left, l_right = _bounds(left)
    r_top, r_bottom, r_left, r_right = _bounds(right)
    return not (l_bottom < r_top or r_bottom < l_top or l_right < r_left or r_right < l_left)
