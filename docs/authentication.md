# Authentication and workbook access

AI Spreadsheet signs users in by email and password before opening the desktop window. Authentication remains separate from workbook permission logic and the UI.

## Identity storage

- With `STORAGE_BACKEND=json`, accounts are stored in `AUTH_USER_STORE` (default `data/users.json`). This file contains user IDs, normalized email addresses, and salted PBKDF2 hashes—never plaintext passwords. It is excluded from Git.
- With `STORAGE_BACKEND=postgres`, accounts use the shared `users` table.

The sign-in dialog supports account creation and login. Successful login produces a signed, expiring in-process session principal. Configure a long random `AUTH_SESSION_SECRET` for shared or production deployments. Development mode generates a random key when none is supplied; those tokens naturally expire when the process closes. Production refuses a missing or short signing secret.

## Workbook roles

- **Owner**: edit workbook content, save, manage sharing, revoke access, and transfer ownership.
- **Editor**: edit and save workbook content but cannot change permissions.
- **Viewer**: open, navigate, copy, and export; the grid and editing actions are read-only.

New and imported workbooks assign the signed-in user as owner. When an authenticated user first opens an older local JSON workbook without an owner, the application claims it for that user. Existing protected workbooks deny users without a role.

An ownership transfer keeps the previous owner as an editor, preventing the workbook from becoming inaccessible before the permission update is saved.

## PostgreSQL enforcement

PostgreSQL workbooks use the permission-aware adapter methods. Access is checked in SQL when opening, owners/editors are required when saving, and editor payloads cannot rewrite the permission set. PostgreSQL workbooks migrated from JSON should be assigned an owner:

```bash
python -m db.json_to_postgres --source-dir data --owner-email owner@example.com --dry-run
python -m db.json_to_postgres --source-dir data --owner-email owner@example.com
```

The local user store is automatically excluded from migration scans.

## Current boundary

This phase provides local and PostgreSQL email/password identity suitable for the desktop application. Enterprise SSO, password-reset token persistence, administrator account recovery, and cross-device token revocation belong to later server/integration phases.
