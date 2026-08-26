"""Optional authenticated collaboration transport for the desktop client."""

from __future__ import annotations

from dataclasses import dataclass
import json
import threading
import time
from typing import Any, Callable, Protocol
from urllib.parse import quote, urlencode, urlparse, urlunparse
import uuid

import httpx
import websocket


@dataclass(slots=True)
class CollaborationIdentity:
    user_id: str
    display_name: str


@dataclass(slots=True)
class PresencePayload:
    current_sheet: str | None = None
    active_range: str | None = None


class CollaborationConflict(RuntimeError):
    def __init__(self, detail: dict[str, Any]) -> None:
        super().__init__(str(detail.get("message") or "Workbook revision conflict."))
        self.detail = detail


class CollaborationClient(Protocol):
    def join_workbook(self, workbook_id: str, identity: CollaborationIdentity,
                      presence: PresencePayload) -> str: ...
    def update_presence(self, presence: PresencePayload) -> None: ...
    def leave_workbook(self) -> None: ...
    def acquire_advisory_lock(self, sheet: str, range_ref: str) -> bool: ...
    def release_advisory_lock(self, sheet: str, range_ref: str) -> None: ...
    def publish_cell_change(self, sheet: str, address: str, value: Any,
                            formula: str | None) -> dict[str, Any]: ...


class RealtimeCollaborationClient:
    """HTTP commands plus a reconnecting WebSocket event subscription."""

    def __init__(self, server_url: str, session_token: str,
                 event_handler: Callable[[dict[str, Any]], None] | None = None,
                 timeout_seconds: float = 5.0) -> None:
        self.server_url = server_url.rstrip("/")
        self.session_token = session_token
        self.event_handler = event_handler or (lambda _event: None)
        self.http = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=timeout_seconds,
            trust_env=False,
        )
        self.workbook_id: str | None = None
        self.identity: CollaborationIdentity | None = None
        self.presence = PresencePayload()
        self.session_id: str | None = None
        self.role: str | None = None
        self.revision = 0
        self._stop = threading.Event()
        self._socket: websocket.WebSocketApp | None = None
        self._socket_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._state_lock = threading.RLock()

    def join_workbook(self, workbook_id: str, identity: CollaborationIdentity,
                      presence: PresencePayload) -> str:
        self.workbook_id = workbook_id
        self.identity = identity
        self.presence = presence
        payload = self._request("POST", f"/api/collaboration/workbooks/{self._key()}/join", json={
            "display_name": identity.display_name,
            "current_sheet": presence.current_sheet,
            "active_range": presence.active_range,
        })
        with self._state_lock:
            self.session_id = str(payload["session_id"])
            self.role = str(payload["role"])
            self.revision = int(payload.get("state", {}).get("revision", 0))
        return self.session_id

    def start(self, workbook_id: str, identity: CollaborationIdentity,
              presence: PresencePayload) -> str:
        session_id = self.join_workbook(workbook_id, identity, presence)
        self._stop.clear()
        self._socket_thread = threading.Thread(target=self._socket_loop, daemon=True)
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._socket_thread.start()
        self._heartbeat_thread.start()
        return session_id

    def update_presence(self, presence: PresencePayload) -> None:
        self.presence = presence
        self._session_request("presence", {
            "current_sheet": presence.current_sheet,
            "active_range": presence.active_range,
        })

    def leave_workbook(self) -> None:
        if self.workbook_id and self.session_id:
            try:
                self._session_request("leave", {})
            except (httpx.HTTPError, RuntimeError):
                pass
        self.session_id = None

    def acquire_advisory_lock(self, sheet: str, range_ref: str) -> bool:
        try:
            self._session_request("locks/acquire", {"sheet_name": sheet, "range_ref": range_ref})
            return True
        except CollaborationConflict:
            return False

    def release_advisory_lock(self, sheet: str, range_ref: str) -> None:
        try:
            self._session_request("locks/release", {"sheet_name": sheet, "range_ref": range_ref})
        except RuntimeError:
            pass

    def publish_cell_change(self, sheet: str, address: str, value: Any,
                            formula: str | None) -> dict[str, Any]:
        with self._state_lock:
            base_revision = self.revision
        try:
            payload = self._session_request("cells", {
                "operation_id": uuid.uuid4().hex,
                "base_revision": base_revision,
                "sheet_name": sheet,
                "address": address,
                "value": value,
                "formula": formula,
            })
        except CollaborationConflict as exc:
            if "current_revision" in exc.detail:
                with self._state_lock:
                    self.revision = int(exc.detail["current_revision"])
                self._emit({"event": "sync.required", "changes": exc.detail.get("changes", [])})
            raise
        change = payload.get("change", {})
        with self._state_lock:
            self.revision = max(self.revision, int(change.get("revision", self.revision)))
        return change

    def stop(self) -> None:
        self._stop.set()
        self.leave_workbook()
        if self._socket:
            self._socket.close()
        self.http.close()

    def _session_request(self, suffix: str, extra: dict[str, Any]) -> dict[str, Any]:
        if not self.session_id:
            raise RuntimeError("No active collaboration session.")
        return self._request(
            "POST", f"/api/collaboration/workbooks/{self._key()}/{suffix}",
            json={"session_id": self.session_id, **extra},
        )

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = self.http.request(method, path, **kwargs)
        if response.status_code == 409:
            detail = response.json().get("detail", {})
            raise CollaborationConflict(detail if isinstance(detail, dict) else {"message": str(detail)})
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text
            raise RuntimeError(str(detail or exc)) from exc
        return response.json()

    def _key(self) -> str:
        if not self.workbook_id:
            raise RuntimeError("No workbook selected for collaboration.")
        return quote(self.workbook_id, safe="")

    def _socket_loop(self) -> None:
        while not self._stop.is_set():
            if not self.session_id:
                time.sleep(1)
                continue
            self._socket = websocket.WebSocketApp(
                self._websocket_url(),
                on_message=self._on_message,
                on_error=lambda _socket, error: self._emit({"event": "connection.error", "detail": str(error)}),
                on_close=lambda _socket, code, reason: self._emit({"event": "connection.closed", "code": code, "detail": reason}),
            )
            self._socket.run_forever(ping_interval=20, ping_timeout=10, http_proxy_host=None)
            if not self._stop.wait(2):
                self._emit({"event": "connection.reconnecting"})

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(30):
            if not self.session_id:
                continue
            try:
                self._session_request("heartbeat", {
                    "current_sheet": self.presence.current_sheet,
                    "active_range": self.presence.active_range,
                })
            except RuntimeError as exc:
                self._emit({"event": "connection.error", "detail": str(exc)})
                if "access denied" in str(exc).casefold():
                    self.session_id = None
                    if self._socket:
                        self._socket.close()
                    self._emit({"event": "access.revoked"})
                    continue
                if "not found" in str(exc).casefold() or "expired" in str(exc).casefold():
                    self._rejoin()

    def _rejoin(self) -> None:
        if self._stop.is_set() or not self.workbook_id or not self.identity:
            return
        try:
            self.join_workbook(self.workbook_id, self.identity, self.presence)
        except (httpx.HTTPError, RuntimeError) as exc:
            self._emit({"event": "connection.error", "detail": str(exc)})
            return
        if self._socket:
            self._socket.close()
        self._emit({"event": "session.rejoined", "revision": self.revision})

    def _websocket_url(self) -> str:
        parsed = urlparse(self.server_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        query = urlencode({"token": self.session_token, "session_id": self.session_id or ""})
        path = f"{parsed.path.rstrip('/')}/ws/collaboration/workbooks/{self._key()}"
        return urlunparse((scheme, parsed.netloc, path, "", query, ""))

    def _on_message(self, _socket, message: str) -> None:
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return
        revision = event.get("change", {}).get("revision") if isinstance(event, dict) else None
        if revision is not None:
            with self._state_lock:
                self.revision = max(self.revision, int(revision))
        if isinstance(event, dict):
            self._emit(event)

    def _emit(self, event: dict[str, Any]) -> None:
        try:
            self.event_handler(event)
        except Exception:
            pass
