"""Authenticated FastAPI collaboration server."""

from __future__ import annotations

import uuid
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.auth.service import SessionPrincipal, SessionTokenManager
from server.authorization import CollaborationAuthorizer, create_authorizer
from server.collaboration import CollaborationHub


app = FastAPI(title="AI Spreadsheet Collaboration Server")
hub = CollaborationHub(presence_ttl_seconds=int(os.getenv("COLLAB_PRESENCE_TTL_SECONDS", "90")))


class JoinRequest(BaseModel):
    display_name: str = Field(default="", max_length=120)
    current_sheet: str | None = Field(default=None, max_length=120)
    active_range: str | None = Field(default=None, max_length=80)


class SessionRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=128)
    current_sheet: str | None = Field(default=None, max_length=120)
    active_range: str | None = Field(default=None, max_length=80)


class LockRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=128)
    sheet_name: str = Field(min_length=1, max_length=120)
    range_ref: str = Field(min_length=2, max_length=80)


class CellUpdateRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=128)
    operation_id: str = Field(min_length=8, max_length=128)
    base_revision: int = Field(ge=0)
    sheet_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=2, max_length=32)
    value: Any = None
    formula: str | None = Field(default=None, max_length=32767)


def _token_manager() -> SessionTokenManager:
    manager = getattr(app.state, "session_token_manager", None)
    if manager is None:
        manager = SessionTokenManager()
        app.state.session_token_manager = manager
    return manager


def _authorizer() -> CollaborationAuthorizer:
    authorizer = getattr(app.state, "collaboration_authorizer", None)
    if authorizer is None:
        authorizer = create_authorizer()
        app.state.collaboration_authorizer = authorizer
    return authorizer


def _validate_token(token: str) -> SessionPrincipal:
    principal = _token_manager().validate_token(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="A valid, unexpired session token is required.")
    return principal


def require_principal(authorization: str | None = Header(default=None)) -> SessionPrincipal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer authentication is required.")
    return _validate_token(authorization[7:].strip())


def _role_or_403(principal: SessionPrincipal, workbook_id: str) -> str:
    role = _authorizer().resolve_role(principal.email, workbook_id)
    if role not in {"owner", "editor", "viewer"}:
        raise HTTPException(status_code=403, detail="Workbook access denied.")
    return role


def _session_or_404(workbook_id: str, session_id: str, principal: SessionPrincipal):
    current_role = _role_or_403(principal, workbook_id)
    session = hub.session(workbook_id, session_id, principal.user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Collaboration session was not found or expired.")
    session.role = current_role
    return session


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "transport": "websocket", "mode": "revisioned-collaboration"}


@app.get("/api/collaboration/workbooks/{workbook_id}")
def get_workbook_state(workbook_id: str, principal: SessionPrincipal = Depends(require_principal)):
    _role_or_403(principal, workbook_id)
    return hub.snapshot(workbook_id)


@app.post("/api/collaboration/workbooks/{workbook_id}/join")
async def join_workbook(workbook_id: str, request: JoinRequest,
                        principal: SessionPrincipal = Depends(require_principal)):
    role = _role_or_403(principal, workbook_id)
    session_id = uuid.uuid4().hex
    presence = await hub.join(
        workbook_id=workbook_id,
        user_id=principal.user_id,
        email=principal.email,
        display_name=request.display_name.strip() or principal.email,
        session_id=session_id,
        role=role,
        current_sheet=request.current_sheet,
        active_range=request.active_range,
    )
    return {"session_id": session_id, "role": role, "presence": presence.to_public_dict(),
            "state": hub.snapshot(workbook_id)}


@app.post("/api/collaboration/workbooks/{workbook_id}/leave")
async def leave_workbook(workbook_id: str, request: SessionRequest,
                         principal: SessionPrincipal = Depends(require_principal)):
    _role_or_403(principal, workbook_id)
    if not await hub.leave(workbook_id, request.session_id, principal.user_id):
        raise HTTPException(status_code=404, detail="Collaboration session was not found.")
    return {"ok": True}


@app.post("/api/collaboration/workbooks/{workbook_id}/presence")
async def update_presence(workbook_id: str, request: SessionRequest,
                          principal: SessionPrincipal = Depends(require_principal)):
    _role_or_403(principal, workbook_id)
    updated = await hub.update_presence(
        workbook_id=workbook_id, session_id=request.session_id, user_id=principal.user_id,
        current_sheet=request.current_sheet, active_range=request.active_range,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Collaboration session was not found or expired.")
    return {"presence": updated.to_public_dict()}


@app.post("/api/collaboration/workbooks/{workbook_id}/heartbeat")
async def heartbeat(workbook_id: str, request: SessionRequest,
                    principal: SessionPrincipal = Depends(require_principal)):
    await hub.expire_stale_sessions(workbook_id)
    _session_or_404(workbook_id, request.session_id, principal)
    return await update_presence(workbook_id, request, principal)


@app.post("/api/collaboration/workbooks/{workbook_id}/locks/acquire")
async def acquire_lock(workbook_id: str, request: LockRequest,
                       principal: SessionPrincipal = Depends(require_principal)):
    session = _session_or_404(workbook_id, request.session_id, principal)
    if session.role not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="Viewers cannot acquire editing locks.")
    try:
        success, lock = await hub.acquire_lock(
            workbook_id=workbook_id, user_id=principal.user_id,
            session_id=request.session_id, display_name=session.display_name,
            sheet_name=request.sheet_name, range_ref=request.range_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not success:
        raise HTTPException(status_code=409, detail={"message": "Range overlaps another user's lock.",
                                                     "held_by": lock.to_public_dict() if lock else None})
    return {"lock": lock.to_public_dict() if lock else None}


@app.post("/api/collaboration/workbooks/{workbook_id}/locks/release")
async def release_lock(workbook_id: str, request: LockRequest,
                       principal: SessionPrincipal = Depends(require_principal)):
    _session_or_404(workbook_id, request.session_id, principal)
    released = await hub.release_lock(
        workbook_id=workbook_id, user_id=principal.user_id, session_id=request.session_id,
        sheet_name=request.sheet_name, range_ref=request.range_ref,
    )
    if not released:
        raise HTTPException(status_code=404, detail="No matching lock is held by this session.")
    return {"ok": True}


@app.post("/api/collaboration/workbooks/{workbook_id}/cells")
async def update_cell(workbook_id: str, request: CellUpdateRequest,
                      principal: SessionPrincipal = Depends(require_principal)):
    session = _session_or_404(workbook_id, request.session_id, principal)
    if session.role not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="Viewers cannot publish cell changes.")
    if request.formula is not None and not request.formula.startswith("="):
        raise HTTPException(status_code=422, detail="Formula text must start with '='.")
    blocking_lock = hub.conflicting_lock(
        workbook_id, request.sheet_name, request.address, request.session_id
    )
    if blocking_lock:
        raise HTTPException(
            status_code=409,
            detail={"message": "Cell is covered by another user's advisory lock.",
                    "held_by": blocking_lock.to_public_dict()},
        )
    try:
        accepted, change, conflict = await hub.apply_cell_change(
            workbook_id=workbook_id, operation_id=request.operation_id,
            base_revision=request.base_revision, sheet_name=request.sheet_name,
            address=request.address, value=request.value, formula=request.formula,
            user_id=principal.user_id, session_id=request.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not accepted:
        raise HTTPException(status_code=409, detail={"message": "Workbook revision conflict.", **(conflict or {})})
    return {"change": change.to_public_dict() if change else None}


@app.websocket("/ws/collaboration/workbooks/{workbook_id}")
async def collaboration_ws(websocket: WebSocket, workbook_id: str, token: str = "",
                           session_id: str = "") -> None:
    principal = _token_manager().validate_token(token)
    if principal is None:
        await websocket.close(code=4401, reason="Authentication required")
        return
    role = _authorizer().resolve_role(principal.email, workbook_id)
    session = hub.session(workbook_id, session_id, principal.user_id)
    if role not in {"owner", "editor", "viewer"} or session is None:
        await websocket.close(code=4403, reason="Workbook session required")
        return
    await websocket.accept()
    hub.register_socket(workbook_id, websocket)
    await websocket.send_json({"event": "connected", "state": hub.snapshot(workbook_id)})
    try:
        while True:
            event = await websocket.receive_json()
            await hub.expire_stale_sessions(workbook_id)
            if hub.session(workbook_id, session_id, principal.user_id) is None:
                await websocket.close(code=4408, reason="Collaboration session expired")
                return
            current_role = _authorizer().resolve_role(principal.email, workbook_id)
            if current_role not in {"owner", "editor", "viewer"}:
                await websocket.close(code=4403, reason="Workbook access revoked")
                return
            session.role = current_role
            event_type = event.get("event")
            if event_type in {"heartbeat", "presence.update"}:
                await hub.update_presence(
                    workbook_id=workbook_id, session_id=session_id, user_id=principal.user_id,
                    current_sheet=event.get("current_sheet"), active_range=event.get("active_range"),
                )
            else:
                await websocket.send_json({"event": "warning", "detail": "Use authenticated REST endpoints for locks and cell updates."})
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister_socket(workbook_id, websocket)
        await hub.leave(workbook_id, session_id, principal.user_id)
