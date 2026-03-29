"""Collaboration server starter implementation using FastAPI + WebSockets."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from server.collaboration import CollaborationHub

app = FastAPI(title="AI Spreadsheet Collaboration Server")
hub = CollaborationHub()


class JoinRequest(BaseModel):
    """Payload for joining a workbook collaboration session."""

    user_id: str
    display_name: str
    current_sheet: str | None = None
    active_range: str | None = None


class PresenceUpdateRequest(BaseModel):
    """Payload for updating current sheet and focused cell/range visibility."""

    user_id: str
    current_sheet: str | None = None
    active_range: str | None = None


class LockRequest(BaseModel):
    """Payload for lock acquisition/release requests."""

    user_id: str
    display_name: str = Field(default="")
    sheet_name: str
    range_ref: str


@app.get("/health")
def health() -> dict[str, str]:
    """Health endpoint for liveness checks."""
    return {"status": "ok", "transport": "websocket", "mode": "starter-collaboration"}


@app.get("/api/collaboration/workbooks/{workbook_id}")
def get_workbook_state(workbook_id: str) -> dict[str, object]:
    """Return current participant and lock state for a workbook."""
    return hub.snapshot(workbook_id)


@app.post("/api/collaboration/workbooks/{workbook_id}/join")
async def join_workbook(workbook_id: str, request: JoinRequest) -> dict[str, object]:
    """Register a user presence entry for a workbook collaboration session."""
    session_id = uuid.uuid4().hex
    presence = await hub.join(
        workbook_id=workbook_id,
        user_id=request.user_id,
        display_name=request.display_name,
        session_id=session_id,
        current_sheet=request.current_sheet,
        active_range=request.active_range,
    )
    return {"session_id": session_id, "presence": presence.to_public_dict()}


@app.post("/api/collaboration/workbooks/{workbook_id}/leave")
async def leave_workbook(workbook_id: str, request: PresenceUpdateRequest) -> dict[str, bool]:
    """Remove a user from workbook presence tracking."""
    await hub.leave(workbook_id, request.user_id)
    return {"ok": True}


@app.post("/api/collaboration/workbooks/{workbook_id}/presence")
async def update_presence(workbook_id: str, request: PresenceUpdateRequest) -> dict[str, object]:
    """Update currently viewed sheet and active cell/range for a connected user."""
    updated = await hub.update_presence(
        workbook_id=workbook_id,
        user_id=request.user_id,
        current_sheet=request.current_sheet,
        active_range=request.active_range,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User is not in an active workbook session.")
    return {"presence": updated.to_public_dict()}


@app.post("/api/collaboration/workbooks/{workbook_id}/locks/acquire")
async def acquire_lock(workbook_id: str, request: LockRequest) -> dict[str, object]:
    """Acquire (or refresh) an advisory lock for a sheet range."""
    success, lock = await hub.acquire_lock(
        workbook_id=workbook_id,
        user_id=request.user_id,
        display_name=request.display_name or request.user_id,
        sheet_name=request.sheet_name,
        range_ref=request.range_ref,
    )
    if not success:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Lock already held by another user.",
                "held_by": lock.to_public_dict() if lock else None,
            },
        )
    return {"lock": lock.to_public_dict() if lock else None}


@app.post("/api/collaboration/workbooks/{workbook_id}/locks/release")
async def release_lock(workbook_id: str, request: LockRequest) -> dict[str, bool]:
    """Release an advisory lock when the holding user is done editing."""
    released = await hub.release_lock(
        workbook_id=workbook_id,
        user_id=request.user_id,
        sheet_name=request.sheet_name,
        range_ref=request.range_ref,
    )
    if not released:
        raise HTTPException(status_code=404, detail="No matching lock held by this user.")
    return {"ok": True}


@app.websocket("/ws/collaboration/workbooks/{workbook_id}")
async def collaboration_ws(websocket: WebSocket, workbook_id: str) -> None:
    """Push near real-time presence/lock events to subscribed clients."""
    await websocket.accept()
    hub.register_socket(workbook_id, websocket)
    await websocket.send_json({"event": "connected", "state": hub.snapshot(workbook_id)})

    try:
        while True:
            event = await websocket.receive_json()
            event_type = event.get("event")

            if event_type == "presence.update":
                await hub.update_presence(
                    workbook_id=workbook_id,
                    user_id=event.get("user_id", ""),
                    current_sheet=event.get("current_sheet"),
                    active_range=event.get("active_range"),
                )
            elif event_type == "lock.acquire":
                await hub.acquire_lock(
                    workbook_id=workbook_id,
                    user_id=event.get("user_id", ""),
                    display_name=event.get("display_name", event.get("user_id", "")),
                    sheet_name=event.get("sheet_name", ""),
                    range_ref=event.get("range_ref", ""),
                )
            elif event_type == "lock.release":
                await hub.release_lock(
                    workbook_id=workbook_id,
                    user_id=event.get("user_id", ""),
                    sheet_name=event.get("sheet_name", ""),
                    range_ref=event.get("range_ref", ""),
                )
            else:
                await websocket.send_json({
                    "event": "warning",
                    "detail": "Unsupported event. Supported: presence.update, lock.acquire, lock.release.",
                })
    except WebSocketDisconnect:
        hub.unregister_socket(workbook_id, websocket)
