# AI Spreadsheet

AI Spreadsheet is a **desktop-first Python spreadsheet application scaffold** built with **PySide6** and modular architecture.

> ⚠️ **Scaffold status:** This repository currently provides a production-minded MVP skeleton and placeholders for some advanced features (auth flows, collaboration server, email notifications), while JSON and PostgreSQL workbook storage backends are now both available behind a shared storage abstraction.

## Project tree

```text
AI_Spreadsheet/
├── app/
│   ├── main.py
│   ├── auth/
│   ├── engine/
│   ├── formulas/
│   ├── models/
│   ├── permissions/
│   ├── services/
│   ├── storage/
│   └── ui/
├── data/
├── db/
├── docs/
├── plugins/
├── server/
└── tests/
```

## MVP scaffold includes

- Desktop shell (`PySide6`) with:
  - main window
  - menu bar (file/edit/sheet actions)
  - toolbar groups for file and edit actions
  - formula bar with active-cell name box
  - worksheet grid with row/column headers
  - sheet tabs with add/rename/duplicate/delete actions
  - status bar with cell position and edit mode indicators
  - keyboard shortcuts for common actions (save, copy/paste, undo/redo)
- Workbook, worksheet, and cell data models.
- Local JSON storage adapter (load/save).
- PostgreSQL storage adapter using normalized schema in `db/schema.sql`.
- JSON workbook schema documentation in `docs/workbook_json_structure.md`.
- Excel/CSV conversion service for practical workbook interchange:
  - import `.xlsx` with multi-sheet support
  - export `.xlsx` with sheet name sanitization for Excel constraints
  - import `.csv` into a single worksheet
  - export active sheet to `.csv`
- Starter formula engine with:
  - same-sheet references (e.g., `=A1+B2`)
  - dynamic discovery of built-in `builtin_*.py` formula modules
  - runtime plugin function loading from `plugins/`
- Plugin formula loading from `plugins/`.
- Placeholder/scaffold modules for:
  - Authentication flows
  - Collaboration server
  - Email notifications


## Reliability and hardening status

The current scaffold includes lightweight but realistic automated coverage for core reliability paths:

- formula engine parsing/evaluation and plugin loading (`tests/test_formula_engine.py`)
- JSON workbook storage validation and round-trip persistence (`tests/test_json_storage.py`)
- workbook model serialization defaults (`tests/test_workbook_model.py`)
- auth/session and permission workflows (`tests/test_auth_permissions.py`)
- PostgreSQL configuration parsing/validation (`tests/test_postgres_config.py`)

Validation hardening included in this stage:

- stricter auth config validation (`AUTH_PASSWORD_ITERATIONS`, `AUTH_SESSION_TTL_SECONDS`)
- safer password hash verification for malformed hashes
- stronger session token payload checks
- stricter PostgreSQL env parsing and `POSTGRES_SSLMODE` validation

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m app.main
```

Run tests:

```bash
pytest -q
```

## Storage backend switching

Storage adapters are selected via `STORAGE_BACKEND`:

- `json` (default, local-first)
- `postgres` (alternative backend)

Use `app.storage.get_workbook_storage()` to resolve the adapter from env-based configuration.

```bash
# default local-first mode
STORAGE_BACKEND=json

# PostgreSQL mode
STORAGE_BACKEND=postgres
```

## PostgreSQL backend setup

### 1) Configure environment

Copy the sample env file and update database credentials:

```bash
cp .env.example .env
```

Required PostgreSQL env vars (no hardcoded credentials in code):

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`

### 2) Initialize schema

```bash
python -m db.init_postgres
```

This applies `db/schema.sql`, which includes tables for:

- `users`
- `workbooks`
- `sheets`
- `cells`
- `workbook_permissions`
- `workbook_sessions`

### 3) Migrate existing JSON files (optional)

```bash
python -m db.json_to_postgres
```

By default this migrates `data/*.json` and stores each workbook in PostgreSQL using the JSON filename stem as the workbook `external_key`.


## Authentication and sharing model

Authentication is now scaffolded as reusable services in `app/auth/service.py` with:

- email-based registration and login
- PBKDF2-SHA256 password hashing (`PasswordHasher`)
- signed session tokens (`SessionTokenManager`)
- identity-provider abstraction (`IdentityProvider`) and repository abstraction (`UserRepository`) so external identity providers or database-backed auth can be integrated later without changing UI code
- optional PostgreSQL-backed user repository (`PostgresUserRepository`) for persistent email/password accounts

Environment variables for auth are configured via `.env`:

- `AUTH_IDENTITY_PROVIDER` (`local` scaffold default)
- `AUTH_SESSION_SECRET` (required for token signing)
- `AUTH_SESSION_TTL_SECONDS`
- `AUTH_PASSWORD_ITERATIONS`
- `AUTH_PASSWORD_PEPPER` (optional)

Workbook sharing and role checks are handled separately in `app/permissions/service.py` via `PermissionService`:

- `create_workbook_with_owner(...)` to create workbook + owner assignment
- owner-controlled sharing workflows: `invite_user_as_owner(...)`, `grant_editor_access_as_owner(...)`, `grant_viewer_access_as_owner(...)`, `revoke_access_as_owner(...)`
- role checks via `can_view(...)` / `can_edit(...)` and lookup via `resolve_role(...)`

Roles are limited to `owner`, `editor`, and `viewer`, and are intended to be reusable across both JSON-local and PostgreSQL-backed modes.

## Email notifications (sharing + auth scaffold)

The email notification module is implemented in `app/services/email_service.py` and designed to stay swappable across providers.

Capabilities in this stage:

- workbook invitation email
- access granted email
- access removed email
- optional password reset email scaffold

Text templates are in `app/services/email_templates/`:

- `workbook_invitation.txt`
- `access_granted.txt`
- `access_removed.txt`
- `password_reset.txt`

### Provider configuration

Configure in `.env` (no hardcoded secrets):

- `EMAIL_ENABLED` — global on/off switch
- `EMAIL_DEV_MODE` — safe local mode that captures/logs outgoing emails without external delivery
- `EMAIL_PROVIDER` — `smtp` or `api`
- `EMAIL_FROM`

SMTP mode:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`

API mode:

- `EMAIL_API_ENDPOINT`
- `EMAIL_API_TOKEN`
- `EMAIL_API_TIMEOUT_SECONDS`

Optional link base:

- `APP_BASE_URL`

### Usage from sharing workflows

Use `SharingWorkflowService` (`app/permissions/service.py`) to keep authorization rules and notifications together:

- `invite_user(...)` updates permissions and sends invitation email
- `grant_access(...)` updates role and sends access-granted email
- `revoke_access(...)` removes role and sends access-removed email

### Usage from auth workflows

`AuthService.send_password_reset_email(...)` is a scaffold helper that:

1. validates that the account exists
2. creates an opaque reset token
3. sends password reset instructions through `EmailNotificationService`

Persisting and validating reset tokens is intentionally left for a later stage.

## PostgreSQL authorization support

`app/permissions/service.py` now includes `PostgresPermissionService` for role checks against PostgreSQL-backed workbooks (`owner` / `editor` / `viewer`).

This keeps authorization logic separate from UI and separate from workbook model/business logic.


## Collaboration server (starter, not full co-editing)

The collaboration backend now lives in `server/main.py` + `server/collaboration.py` and provides a realistic starter architecture separated from the desktop UI layer:

- FastAPI REST endpoints for workbook join/leave, presence updates, lock acquire/release, and state snapshot retrieval.
- WebSocket subscription channel at `/ws/collaboration/workbooks/{workbook_id}` for near real-time participant and advisory-lock events.
- In-memory workbook session tracking keyed by workbook id.
- User presence payloads tracking who has a workbook open, current sheet visibility, and active cell/range visibility.
- Advisory lock scaffold (`sheet + range`) to reduce edit collisions before full merge/conflict resolution is implemented.

Current REST endpoints:

- `GET /health`
- `GET /api/collaboration/workbooks/{workbook_id}`
- `POST /api/collaboration/workbooks/{workbook_id}/join`
- `POST /api/collaboration/workbooks/{workbook_id}/leave`
- `POST /api/collaboration/workbooks/{workbook_id}/presence`
- `POST /api/collaboration/workbooks/{workbook_id}/locks/acquire`
- `POST /api/collaboration/workbooks/{workbook_id}/locks/release`

Client/server separation:

- Desktop-side collaboration contract scaffold is defined in `app/services/collaboration_client.py` as a protocol + payload dataclasses.
- The PySide6 UI is not tightly coupled to FastAPI transport details.

### Collaboration limitations (explicit)

This stage intentionally does **not** claim full Google Sheets-style collaboration. Specifically:

- No OT/CRDT algorithm yet; simultaneous cell edits are not merged automatically.
- Locks are advisory starter controls, not hard transactional guarantees.
- Server session state is currently in-memory (restart clears presence/locks).
- No durable event log or replay stream yet.
- No websocket auth handshake yet; integrate with auth/session tokens in a later stage.

Run the collaboration server locally:

```bash
uvicorn server.main:app --reload --port 8000
```

## Formula functions and plugins

Built-in formula modules live in `app/formulas/` and are loaded dynamically when the app starts.  
Any uppercase function in `builtin_*.py` files is automatically registered (for example: `SUM`, `IF`, `CONCAT`).

To add a custom function:

1. Create a `.py` file in `plugins/` (or another folder configured via `PluginLoader`).
2. Define uppercase functions only for formulas you want exposed.
3. Start the app; plugin functions are loaded at runtime.

Example plugin function:

```python
def DOUBLE(value):  # usable as =DOUBLE(21)
    return float(value) * 2
```

## Excel/CSV compatibility notes (practical, not perfect parity)

The app provides a practical import/export layer in `app/services/file_conversion.py` and intentionally does **not** claim full Excel parity.

### `.xlsx` import currently preserves (where available)
- Workbook sheet order and sheet names.
- Cell values.
- Cell formulas beginning with `=`.
- Cached formula results when present in the source workbook.
- Core formatting fields:
  - number format
  - bold / italic / underline
  - font color
  - solid fill color
  - horizontal/vertical alignment
  - wrap text

### `.xlsx` export currently preserves
- Sheet names (sanitized for Excel-invalid characters and uniqueness).
- Cell values and formulas.
- The same core formatting fields listed above when they exist in workbook cell formatting payloads.

### `.csv` import/export behavior
- CSV is handled as **single-sheet** interchange.
- Import creates one worksheet from the CSV rows/columns.
- Export writes one worksheet (the active sheet in the UI).
- Formula-like text beginning with `=` is preserved as formulas.
- Scalar parsing on CSV import is best-effort (integers, floats, booleans, otherwise text).

### Known limitations
- No support yet for pivot tables, charts, merged cells, comments, validation rules, macros, images, frozen panes, or conditional formatting rules.
- Formula recalculation depends on this app's formula engine; Excel-only functions may not evaluate equivalently.
- Cached formula values in imported `.xlsx` files depend on what was stored by the originating spreadsheet application.
