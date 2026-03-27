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
  - menu bar
  - toolbar
  - formula bar
  - worksheet grid
  - sheet tabs
  - status bar
- Workbook, worksheet, and cell data models.
- Local JSON storage adapter (load/save).
- Starter formula engine scaffold with dynamic built-in formula registration.
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

## Notes on scaffolded features

- `app/storage/postgres_storage.py`: interface placeholder only.
- `app/auth/service.py`: login/registration flow placeholder only.
- `app/permissions/service.py`: role-check workflows placeholder only.
- `app/services/email_service.py`: outbound email placeholder only.
- `server/main.py`: collaboration API skeleton with health endpoint only.

These are intentionally separated into modules so future milestones can be implemented without re-architecting the desktop app.
