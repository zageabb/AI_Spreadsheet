"""Tests for collaboration starter server session/presence/locking behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from server.main import app


def test_join_presence_update_and_leave_round_trip():
    client = TestClient(app)

    join_response = client.post(
        "/api/collaboration/workbooks/book-1/join",
        json={
            "user_id": "u-1",
            "display_name": "Alice",
            "current_sheet": "Sheet1",
            "active_range": "A1",
        },
    )
    assert join_response.status_code == 200
    join_payload = join_response.json()
    assert join_payload["presence"]["display_name"] == "Alice"

    update_response = client.post(
        "/api/collaboration/workbooks/book-1/presence",
        json={"user_id": "u-1", "current_sheet": "Sheet2", "active_range": "C3:D6"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["presence"]["current_sheet"] == "Sheet2"

    state_response = client.get("/api/collaboration/workbooks/book-1")
    assert state_response.status_code == 200
    state = state_response.json()
    assert len(state["participants"]) == 1
    assert state["participants"][0]["active_range"] == "C3:D6"
    assert state["capabilities"]["collaborative_cell_edit_merging"] is False

    leave_response = client.post(
        "/api/collaboration/workbooks/book-1/leave",
        json={"user_id": "u-1", "current_sheet": None, "active_range": None},
    )
    assert leave_response.status_code == 200


def test_advisory_lock_conflict_and_release():
    client = TestClient(app)

    client.post(
        "/api/collaboration/workbooks/book-2/join",
        json={"user_id": "owner", "display_name": "Owner", "current_sheet": "Sheet1", "active_range": "A1"},
    )
    client.post(
        "/api/collaboration/workbooks/book-2/join",
        json={"user_id": "editor", "display_name": "Editor", "current_sheet": "Sheet1", "active_range": "A1"},
    )

    lock_response = client.post(
        "/api/collaboration/workbooks/book-2/locks/acquire",
        json={"user_id": "owner", "display_name": "Owner", "sheet_name": "Sheet1", "range_ref": "A1:B2"},
    )
    assert lock_response.status_code == 200

    conflict_response = client.post(
        "/api/collaboration/workbooks/book-2/locks/acquire",
        json={"user_id": "editor", "display_name": "Editor", "sheet_name": "Sheet1", "range_ref": "A1:B2"},
    )
    assert conflict_response.status_code == 409

    release_response = client.post(
        "/api/collaboration/workbooks/book-2/locks/release",
        json={"user_id": "owner", "display_name": "Owner", "sheet_name": "Sheet1", "range_ref": "A1:B2"},
    )
    assert release_response.status_code == 200


def test_websocket_receives_presence_events():
    client = TestClient(app)

    with client.websocket_connect("/ws/collaboration/workbooks/book-3") as websocket:
        connected_payload = websocket.receive_json()
        assert connected_payload["event"] == "connected"

        client.post(
            "/api/collaboration/workbooks/book-3/join",
            json={"user_id": "u-3", "display_name": "Casey", "current_sheet": "Sheet1", "active_range": "B4"},
        )
        joined_payload = websocket.receive_json()
        assert joined_payload["event"] == "presence.joined"
        assert joined_payload["presence"]["user_id"] == "u-3"
