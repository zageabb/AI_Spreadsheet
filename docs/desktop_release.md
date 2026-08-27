# Desktop recovery and release builds

## Autosave and crash recovery

Phase 10 writes a local recovery snapshot while an editable workbook has unsaved changes. It does not overwrite the primary JSON/PostgreSQL workbook and it does not mark the workbook as saved.

Configuration:

- `AUTOSAVE_ENABLED` — enables recovery snapshots; defaults to `true`
- `AUTOSAVE_INTERVAL_SECONDS` — snapshot interval; minimum 15 seconds, default 60
- `AUTOSAVE_DIR` — local snapshot directory; defaults to `data/autosave`

Snapshots are scoped to the signed-in email identity. At startup, the newest available snapshot for that user is offered for recovery. A successful normal save removes its recovery snapshot. Choosing **Discard** when closing also removes the current snapshot.

The **File → Open Recent** menu retains up to eight local JSON workbook paths using platform-native Qt settings. PostgreSQL workbook keys are deliberately excluded.

## Release-candidate build

Install build dependencies and create a platform package:

```bash
python -m pip install -r requirements-build.txt
python scripts/build_release.py
```

The build runs from `AI_Spreadsheet.spec`, includes dynamically discovered formula modules and email templates, and creates:

- `dist/AI-Spreadsheet.zip`
- `dist/AI-Spreadsheet.zip.sha256`

GitHub Actions can build Windows, macOS and Ubuntu artifacts either manually or when a `v*` tag is pushed. Production environment values and secrets are intentionally not bundled. Each package should be smoke-tested on its target OS before being promoted from release candidate.

Ubuntu installations require the normal Qt desktop runtime libraries (`libegl1`, `libgl1`, and the XCB helper libraries installed by the release workflow). These remain operating-system dependencies rather than being copied into the application archive.
