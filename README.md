# AI Spreadsheet

AI Spreadsheet is a **desktop-first Python spreadsheet application scaffold** built with **PySide6** and modular architecture.

> ⚠️ **Scaffold status:** This repository currently provides a production-minded MVP skeleton and placeholders for advanced features (auth, permissions, PostgreSQL backend, collaboration, and email notifications).

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
- Starter formula engine with:
  - same-sheet references (e.g., `=A1+B2`)
  - dynamic discovery of built-in `builtin_*.py` formula modules
  - runtime plugin function loading from `plugins/`
- Plugin formula loading from `plugins/`.
- Placeholder/scaffold modules for:
  - PostgreSQL storage
  - Authentication
  - Permissions
  - Collaboration server
  - Email notifications

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

## Notes on scaffolded features

- `app/storage/postgres_storage.py`: interface placeholder only.
- `app/auth/service.py`: login/registration flow placeholder only.
- `app/permissions/service.py`: role-check workflows placeholder only.
- `app/services/email_service.py`: outbound email placeholder only.
- `server/main.py`: collaboration API skeleton with health endpoint only.

These are intentionally separated into modules so future milestones can be implemented without re-architecting the desktop app.
