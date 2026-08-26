# Controlled collaboration

AI Spreadsheet remains a local desktop application. Collaboration is an optional coordination service, not a replacement web UI.

## Configure

Install dependencies and configure the desktop and server with the same environment:

```env
AUTH_SESSION_SECRET=replace-with-at-least-32-random-characters
COLLAB_SERVER_URL=http://127.0.0.1:8000
COLLAB_PRESENCE_TTL_SECONDS=90
```

For PostgreSQL sharing, both processes use `STORAGE_BACKEND=postgres` and the same database. For JSON sharing, the server resolves `{workbook_id}.json` under `JSON_DATA_DIR`; arbitrary files elsewhere remain local-only.

Start the server, then launch the desktop normally:

```bash
uvicorn server.main:app --host 127.0.0.1 --port 8000
python -m app.main
```

For remote use, put the server behind HTTPS so the WebSocket uses WSS. Do not expose plain HTTP bearer tokens over an untrusted network.

## Live behaviour

1. The desktop signs in and opens a protected workbook.
2. It joins through authenticated HTTP; the server independently resolves its workbook role.
3. A WebSocket carries presence, lock and cell-change events.
4. Current sheet/range changes update presence and acquire an advisory lock for editable users.
5. An edit is accepted only at the client's known workbook revision. The operation ID makes retries idempotent.
6. A stale revision or another session's overlapping lock returns `409 Conflict`, including recent changes for catch-up.
7. Heartbeats remove abandoned sessions; the client reconnects and consumes the bounded recent-change snapshot.

Viewers receive updates but cannot acquire locks or publish changes. Editors can change cells but cannot alter workbook permissions. Owners retain sharing control.

## Deliberate limitations

- This is not Google Sheets-style character-level co-authoring and does not use CRDT or operational transforms.
- The server coordinates cell events but does not durably save workbook content.
- Presence, locks, revision numbers and recent events reset when the server restarts.
- Conflicting edits are rejected and surfaced to the user rather than silently merged.
- Recent catch-up history is bounded; clients offline for a long time should reopen the durable workbook.

These boundaries keep conflict behaviour understandable while leaving a clean route to a durable event store or CRDT layer later.
