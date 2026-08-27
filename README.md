# AI Spreadsheet

AI Spreadsheet is a **desktop-first Python spreadsheet application scaffold** built with **PySide6** and modular architecture.

> ⚠️ **Development status:** The desktop spreadsheet, authentication, permissions and controlled live collaboration are functional. Email delivery and several advanced Excel features remain staged work.

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
  - email/password sign-in and account creation
  - owner-only workbook sharing and ownership transfer
  - access-aware owner, editor, and read-only viewer modes
- Workbook, worksheet, and cell data models.
- Local JSON storage adapter (load/save).
- PostgreSQL storage adapter using the normalized, permission-aware schema in `db/schema.sql`.
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
Unknown backend names fail fast instead of silently falling back to local storage.

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
- `POSTGRES_CONNECT_TIMEOUT`
- `POSTGRES_APPLICATION_NAME`

### 2) Initialize schema

```bash
python -m db.init_postgres --check
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
python -m db.json_to_postgres --source-dir data --dry-run
python -m db.json_to_postgres --source-dir data
```

By default this migrates `data/*.json` and stores each workbook in PostgreSQL using the JSON filename stem as the workbook `external_key`.
Use `--key-prefix` to namespace imported keys and `--continue-on-error` for a complete migration report.

When PostgreSQL is selected, desktop Open and Save prompt for the workbook's stable external key. Excel and CSV import/export continue to use normal files. Service and server integrations can use the adapter's permission-aware load, save, list, and delete methods. See [`docs/postgresql.md`](docs/postgresql.md) for migration, authorization, and production guidance.


## Authentication and sharing model

Authentication is now scaffolded as reusable services in `app/auth/service.py` with:

- email-based registration and login
- PBKDF2-SHA256 password hashing (`PasswordHasher`)
- signed session tokens (`SessionTokenManager`)
- identity-provider abstraction (`IdentityProvider`) and repository abstraction (`UserRepository`) so external identity providers or database-backed auth can be integrated later without changing UI code
- optional PostgreSQL-backed user repository (`PostgresUserRepository`) for persistent email/password accounts
- persistent local hashed-account repository (`JsonUserRepository`) for the default JSON mode
- desktop sign-in/registration dialog and signed-in identity status

Environment variables for auth are configured via `.env`:

- `AUTH_IDENTITY_PROVIDER` (`local` scaffold default)
- `AUTH_SESSION_SECRET` (required for token signing)
- `AUTH_SESSION_TTL_SECONDS`
- `AUTH_RESET_SECRET` (optional separate reset-token signing secret)
- `AUTH_RESET_TTL_SECONDS` (defaults to 30 minutes)
- `AUTH_PASSWORD_ITERATIONS`
- `AUTH_PASSWORD_PEPPER` (optional)
- `AUTH_USER_STORE` (local hashed identity file; defaults to `data/users.json`)

New and imported workbooks assign the signed-in user as owner. Owners can grant viewer/editor access, revoke access, or transfer ownership from the **Access** menu. Viewers get a read-only grid; editors may save content but cannot rewrite permissions. See [`docs/authentication.md`](docs/authentication.md) for the complete flow and deployment boundary.

Workbook sharing and role checks are handled separately in `app/permissions/service.py` via `PermissionService`:

- `create_workbook_with_owner(...)` to create workbook + owner assignment
- owner-controlled sharing workflows: `invite_user_as_owner(...)`, `grant_editor_access_as_owner(...)`, `grant_viewer_access_as_owner(...)`, `revoke_access_as_owner(...)`
- role checks via `can_view(...)` / `can_edit(...)` and lookup via `resolve_role(...)`

Roles are limited to `owner`, `editor`, and `viewer`, and are intended to be reusable across both JSON-local and PostgreSQL-backed modes.

## Email notifications and password recovery

The email notification module is implemented in `app/services/email_service.py` and designed to stay swappable across providers.

Capabilities in this stage:

- workbook invitation email
- access granted email
- access removed email
- expiring password reset email and desktop reset flow

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

`AuthService.send_password_reset_email(...)` and `reset_password(...)` provide a complete local reset flow that:

1. validates that the account exists
2. creates a signed, expiring reset token tied to the current password hash
3. sends password reset instructions through `EmailNotificationService`
4. validates the token and replaces the stored password hash

A successful password change invalidates the token, preventing replay without storing reset tokens. The desktop sign-in dialog includes request-token and apply-token actions. In development mode, messages are captured and logged locally; configure SMTP or the generic API provider for delivery.

### Packaging notes

Include `app/services/email_templates/` in desktop packages. Production builds should set `APP_ENV=production`, disable `EMAIL_DEV_MODE`, provide the sender and provider credentials through the runtime environment, and use signing secrets with at least 32 random characters. Do not bundle `.env`, user stores, or provider credentials in an installer.

## PostgreSQL authorization support

`app/permissions/service.py` now includes `PostgresPermissionService` for role checks against PostgreSQL-backed workbooks (`owner` / `editor` / `viewer`).

This keeps authorization logic separate from UI and separate from workbook model/business logic.


## Excel 365 compatibility

Phase 9 extends the calculation engine with:

- lazy `IF`, `IFERROR`, and `IFNA`, so unused branches do not raise errors
- dynamic-array `SEQUENCE`, `FILTER`, `SORT`, and `UNIQUE`
- automatic multi-cell spilling with `#SPILL!` collision reporting
- downstream recalculation for formulas that reference spilled cells
- structured table-column references such as `SalesTable[Amount]`

XLSX import/export now round-trips Excel tables, table styles, and data-validation rules in addition to formulas, core formatting, frozen panes, merged ranges, filters, widths, and heights. A verified OOXML template layer retains the original package and updates it in place, preserving supported charts, drawings, images and relationships. See [`docs/ooxml_and_custom_functions.md`](docs/ooxml_and_custom_functions.md).

## Custom Python functions

Use **Tools → Custom Python Functions** to write an uppercase function such as `DOUBLE(value)`, validate it, save it locally, and use it immediately as `=DOUBLE(A1)`. The editor blocks imports, file/network/process access, dynamic execution and private attribute access while exposing calculation-oriented built-ins plus `math` and `statistics`. User modules are stored in `CUSTOM_FUNCTIONS_DIR` (`plugins/user` by default) and reloaded at startup. Custom code runs locally, so only save functions you understand.

## Desktop recovery and release candidate

Dirty editable workbooks receive timed local recovery snapshots without overwriting their primary JSON or PostgreSQL record. Recovery is scoped to the signed-in identity and offered at the next startup. The desktop also prompts before closing with unsaved changes, shows recovery state in the status bar, and provides **File → Open Recent** for local JSON workbooks.

Cross-platform PyInstaller configuration, SHA-256 release archives and a Windows/macOS/Ubuntu GitHub Actions build matrix are included. See [`docs/desktop_release.md`](docs/desktop_release.md) for configuration and build commands. Current release version: `0.10.0-rc1`.


## Controlled live collaboration

The optional collaboration backend lives in `server/main.py` + `server/collaboration.py`, while transport remains isolated in `app/services/collaboration_client.py`:

- Bearer-token authentication for every collaboration request and WebSocket.
- Server-side owner/editor/viewer checks using PostgreSQL or server-visible JSON workbooks.
- Multiple independent sessions per user, heartbeat expiry, join/leave and reconnect handling.
- Live presence showing current sheet and active cell/range.
- Overlap-aware advisory locks; viewers cannot lock or publish edits.
- Revisioned, idempotent cell events with explicit HTTP 409 conflict responses and catch-up changes.
- Desktop event application through a Qt signal bridge, with connection and participant status.
- Automatic local-only fallback when `COLLAB_SERVER_URL` is blank or unavailable.

Current REST endpoints:

- `GET /health`
- `GET /api/collaboration/workbooks/{workbook_id}`
- `POST /api/collaboration/workbooks/{workbook_id}/join`
- `POST /api/collaboration/workbooks/{workbook_id}/leave`
- `POST /api/collaboration/workbooks/{workbook_id}/presence`
- `POST /api/collaboration/workbooks/{workbook_id}/heartbeat`
- `POST /api/collaboration/workbooks/{workbook_id}/locks/acquire`
- `POST /api/collaboration/workbooks/{workbook_id}/locks/release`
- `POST /api/collaboration/workbooks/{workbook_id}/cells`

### Collaboration limitations (explicit)

This stage intentionally does **not** claim full Google Sheets-style collaboration. Specifically:

- No OT/CRDT algorithm: concurrent edits from stale revisions are rejected and shown as conflicts.
- Locks are coordination hints, not database transactions.
- Server presence, locks, revisions and the bounded recent-change buffer are in-memory; restart clears them.
- Live cell events are not a durable server-side workbook save. A connected owner/editor must save normally.
- Shared JSON mode requires the workbook to be inside the server's `JSON_DATA_DIR`; PostgreSQL is recommended for multi-machine sharing.

Run the collaboration server locally:

```bash
uvicorn server.main:app --reload --port 8000
```

Set the same strong `AUTH_SESSION_SECRET` for desktop and server, then set the desktop's `COLLAB_SERVER_URL` (for example `http://127.0.0.1:8000`). Leave it blank for normal local-only use. See [`docs/collaboration.md`](docs/collaboration.md).

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
