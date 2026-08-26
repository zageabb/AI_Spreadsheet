from __future__ import annotations

import json

import httpx
import pytest

from app.services.collaboration_client import (
    CollaborationConflict,
    CollaborationIdentity,
    PresencePayload,
    RealtimeCollaborationClient,
)


def test_client_tracks_revision_and_sends_authenticated_updates():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content or b"{}")
        if request.url.path.endswith("/join"):
            return httpx.Response(200, json={"session_id": "a" * 32, "role": "editor",
                                             "state": {"revision": 4}})
        assert payload["base_revision"] == 4
        return httpx.Response(200, json={"change": {"revision": 5, "address": "A1"}})

    client = RealtimeCollaborationClient("http://server.test", "signed-token")
    client.http.close()
    client.http = httpx.Client(base_url="http://server.test",
                               headers={"Authorization": "Bearer signed-token"},
                               transport=httpx.MockTransport(handler))
    client.join_workbook("book-1", CollaborationIdentity("u1", "User"),
                         PresencePayload("Sheet1", "A1"))
    change = client.publish_cell_change("Sheet1", "A1", 12, None)

    assert change["revision"] == 5
    assert client.revision == 5
    assert all(request.headers["authorization"] == "Bearer signed-token" for request in requests)


def test_client_surfaces_revision_conflict_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/join"):
            return httpx.Response(200, json={"session_id": "b" * 32, "role": "editor",
                                             "state": {"revision": 2}})
        return httpx.Response(409, json={"detail": {"message": "Workbook revision conflict.",
                                                     "current_revision": 3}})

    client = RealtimeCollaborationClient("http://server.test", "signed-token")
    client.http.close()
    client.http = httpx.Client(base_url="http://server.test", transport=httpx.MockTransport(handler))
    client.join_workbook("book-1", CollaborationIdentity("u1", "User"), PresencePayload())

    with pytest.raises(CollaborationConflict) as exc_info:
        client.publish_cell_change("Sheet1", "A1", "stale", None)
    assert exc_info.value.detail["current_revision"] == 3
    assert client.revision == 3


def test_client_builds_authenticated_websocket_url():
    client = RealtimeCollaborationClient("https://example.test/base", "token with spaces")
    client.workbook_id = "budget"
    client.session_id = "c" * 32

    url = client._websocket_url()

    assert url.startswith("wss://example.test/base/ws/collaboration/workbooks/budget?")
    assert "token=token+with+spaces" in url
