from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote_plus

from fastapi.testclient import TestClient
import pytest

from app.auth.service import SessionTokenManager, UserRecord
from server.authorization import StaticAuthorizer
from server.collaboration import CollaborationHub, ranges_overlap, utc_now
import server.main as server_main


@pytest.fixture()
def collaboration():
    manager = SessionTokenManager(secret="collaboration-test-secret", ttl_seconds=3600)
    server_main.app.state.session_token_manager = manager
    server_main.app.state.collaboration_authorizer = StaticAuthorizer({
        ("owner@example.com", "book-1"): "owner",
        ("editor@example.com", "book-1"): "editor",
        ("viewer@example.com", "book-1"): "viewer",
    })
    server_main.hub = CollaborationHub()

    def token(user_id: str, email: str) -> str:
        return manager.issue_token(UserRecord(user_id, email, "unused"))

    return TestClient(server_main.app), token


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def join(client: TestClient, token: str, name: str = "User") -> dict:
    response = client.post(
        "/api/collaboration/workbooks/book-1/join",
        headers=headers(token),
        json={"display_name": name, "current_sheet": "Sheet1", "active_range": "A1"},
    )
    assert response.status_code == 200
    return response.json()


def test_endpoints_require_authentication_and_workbook_access(collaboration):
    client, token = collaboration
    assert client.get("/api/collaboration/workbooks/book-1").status_code == 401
    outsider = token("outsider", "outsider@example.com")
    assert client.get("/api/collaboration/workbooks/book-1", headers=headers(outsider)).status_code == 403


def test_two_sessions_for_same_user_presence_and_leave(collaboration):
    client, token = collaboration
    owner = token("owner", "owner@example.com")
    first = join(client, owner, "Owner laptop")
    second = join(client, owner, "Owner desktop")

    state = client.get("/api/collaboration/workbooks/book-1", headers=headers(owner)).json()
    assert len(state["participants"]) == 2
    assert first["session_id"] != second["session_id"]

    updated = client.post(
        "/api/collaboration/workbooks/book-1/presence",
        headers=headers(owner),
        json={"session_id": first["session_id"], "current_sheet": "Costs", "active_range": "C3:D6"},
    )
    assert updated.status_code == 200
    assert updated.json()["presence"]["active_range"] == "C3:D6"

    left = client.post(
        "/api/collaboration/workbooks/book-1/leave",
        headers=headers(owner),
        json={"session_id": first["session_id"]},
    )
    assert left.status_code == 200


def test_overlapping_lock_conflict_and_viewer_denial(collaboration):
    client, token = collaboration
    owner_token = token("owner", "owner@example.com")
    editor_token = token("editor", "editor@example.com")
    viewer_token = token("viewer", "viewer@example.com")
    owner = join(client, owner_token, "Owner")
    editor = join(client, editor_token, "Editor")
    viewer = join(client, viewer_token, "Viewer")

    acquired = client.post(
        "/api/collaboration/workbooks/book-1/locks/acquire", headers=headers(owner_token),
        json={"session_id": owner["session_id"], "sheet_name": "Sheet1", "range_ref": "A1:B4"},
    )
    assert acquired.status_code == 200
    conflict = client.post(
        "/api/collaboration/workbooks/book-1/locks/acquire", headers=headers(editor_token),
        json={"session_id": editor["session_id"], "sheet_name": "Sheet1", "range_ref": "B4:C8"},
    )
    assert conflict.status_code == 409
    blocked_edit = client.post(
        "/api/collaboration/workbooks/book-1/cells", headers=headers(editor_token),
        json={"session_id": editor["session_id"], "operation_id": "locked-edit",
              "base_revision": 0, "sheet_name": "Sheet1", "address": "B2",
              "value": "blocked", "formula": None},
    )
    assert blocked_edit.status_code == 409
    denied = client.post(
        "/api/collaboration/workbooks/book-1/locks/acquire", headers=headers(viewer_token),
        json={"session_id": viewer["session_id"], "sheet_name": "Sheet1", "range_ref": "Z1"},
    )
    assert denied.status_code == 403


def test_revisioned_cell_updates_conflict_and_idempotency(collaboration):
    client, token = collaboration
    owner_token = token("owner", "owner@example.com")
    editor_token = token("editor", "editor@example.com")
    owner = join(client, owner_token, "Owner")
    editor = join(client, editor_token, "Editor")
    payload = {
        "session_id": owner["session_id"], "operation_id": "operation-one",
        "base_revision": 0, "sheet_name": "Sheet1", "address": "A1",
        "value": 42, "formula": None,
    }
    accepted = client.post("/api/collaboration/workbooks/book-1/cells",
                           headers=headers(owner_token), json=payload)
    assert accepted.status_code == 200
    assert accepted.json()["change"]["revision"] == 1
    duplicate = client.post("/api/collaboration/workbooks/book-1/cells",
                            headers=headers(owner_token), json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["change"]["revision"] == 1

    stale = client.post(
        "/api/collaboration/workbooks/book-1/cells", headers=headers(editor_token),
        json={"session_id": editor["session_id"], "operation_id": "operation-two",
              "base_revision": 0, "sheet_name": "Sheet1", "address": "B2",
              "value": "stale", "formula": None},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_revision"] == 1
    assert len(stale.json()["detail"]["changes"]) == 1
    invalid_formula = client.post(
        "/api/collaboration/workbooks/book-1/cells", headers=headers(owner_token),
        json={"session_id": owner["session_id"], "operation_id": "bad-formula",
              "base_revision": 1, "sheet_name": "Sheet1", "address": "C3",
              "value": None, "formula": "SUM(A1:A2)"},
    )
    assert invalid_formula.status_code == 422


def test_websocket_receives_authenticated_cell_event(collaboration):
    client, token = collaboration
    owner_token = token("owner", "owner@example.com")
    owner = join(client, owner_token, "Owner")
    url = (f"/ws/collaboration/workbooks/book-1?token={quote_plus(owner_token)}"
           f"&session_id={owner['session_id']}")
    with client.websocket_connect(url) as websocket:
        assert websocket.receive_json()["event"] == "connected"
        response = client.post(
            "/api/collaboration/workbooks/book-1/cells", headers=headers(owner_token),
            json={"session_id": owner["session_id"], "operation_id": "operation-ws",
                  "base_revision": 0, "sheet_name": "Sheet1", "address": "A1",
                  "value": "live", "formula": None},
        )
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["event"] == "cell.updated"
        assert event["change"]["value"] == "live"


def test_range_overlap_uses_cell_geometry():
    assert ranges_overlap("A1:B4", "B4:C8")
    assert not ranges_overlap("A1:B4", "C1:D4")


def test_revoked_role_is_rechecked_after_join(collaboration):
    client, token = collaboration
    editor_token = token("editor", "editor@example.com")
    editor = join(client, editor_token, "Editor")
    server_main.app.state.collaboration_authorizer.roles.pop(
        ("editor@example.com", "book-1")
    )

    response = client.post(
        "/api/collaboration/workbooks/book-1/cells", headers=headers(editor_token),
        json={"session_id": editor["session_id"], "operation_id": "after-revoke",
              "base_revision": 0, "sheet_name": "Sheet1", "address": "A1",
              "value": "blocked", "formula": None},
    )
    assert response.status_code == 403


def test_heartbeat_expires_abandoned_session(collaboration):
    client, token = collaboration
    owner_token = token("owner", "owner@example.com")
    owner = join(client, owner_token, "Owner")
    server_main.hub._presence["book-1"][owner["session_id"]].last_seen = (
        utc_now() - timedelta(seconds=120)
    )

    response = client.post(
        "/api/collaboration/workbooks/book-1/heartbeat", headers=headers(owner_token),
        json={"session_id": owner["session_id"], "current_sheet": "Sheet1"},
    )
    assert response.status_code == 404
