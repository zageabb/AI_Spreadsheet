# PostgreSQL backend

PostgreSQL is an optional shared persistence backend. Local JSON remains the default and requires no database.

## Configure and initialize

Copy `.env.example` to `.env`, set `STORAGE_BACKEND=postgres`, and replace the sample `POSTGRES_*` values. Credentials are read only from the environment; never commit the populated `.env` file.

Verify connectivity, then apply the idempotent schema:

```bash
python -m db.init_postgres --check
python -m db.init_postgres
```

The schema stores users, workbooks, ordered sheets, sparse cells, permissions, and collaboration presence. Foreign keys cascade workbook content, role and address checks reject invalid records, and a partial unique index allows only one owner per workbook.

## Desktop use

With `STORAGE_BACKEND=json` (the default), Open and Save use local `.json` files. With `STORAGE_BACKEND=postgres`, the same desktop actions prompt for a stable workbook key such as `finance/2026-budget`. Excel and CSV import/export remain file based in both modes.

The adapter also exposes permission-aware server/service methods. Editors can update workbook content but cannot change the persisted permission set through a modified workbook payload:

- `load_workbook_for_user(key, email)` allows owner, editor, or viewer access.
- `save_workbook_for_user(key, workbook, email)` allows owners and editors; a new workbook must name the actor as owner.
- `delete_workbook(key, email)` requires owner access.
- `list_workbooks(email)` returns only workbooks visible to that identity.

The desktop currently uses the unscoped methods because interactive login is a later milestone. Server code should use the permission-aware methods.

## Migrate JSON workbooks

First validate all source files without connecting to PostgreSQL:

```bash
python -m db.json_to_postgres --source-dir data --dry-run
```

Then run the migration:

```bash
python -m db.json_to_postgres --source-dir data --key-prefix imported/ --owner-email owner@example.com
```

The migration is repeatable: a matching external key is updated transactionally. `--owner-email` makes the imported workbooks available through authenticated access. Add `--continue-on-error` to produce a complete failure summary instead of stopping at the first bad workbook. Keep the JSON originals until the migrated workbooks have been opened and verified.

## Production notes

- Use `POSTGRES_SSLMODE=require`, `verify-ca`, or `verify-full` as required by the provider.
- Keep `POSTGRES_CONNECT_TIMEOUT` finite; the default is 10 seconds.
- Use a least-privilege database role and provider-managed backups.
- Apply `db/schema.sql` during deployment before switching the application backend.
- PostgreSQL saves are transactional, so a failed write rolls back rather than leaving a partial workbook.
