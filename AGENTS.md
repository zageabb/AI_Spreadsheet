# AGENTS.md

## Purpose
This repository is building a real Python desktop spreadsheet application with a modular architecture.

## Project intent
Build a cross-platform spreadsheet application in Python with:
- a desktop UI
- local-first JSON storage
- Excel-compatible workflows
- a plugin-based formula engine
- an upgrade path to PostgreSQL
- user authentication and workbook sharing
- a collaboration server starter
- modular email notifications

## Mandatory architectural rules
- Keep this as a **desktop Python application**
- Do **not** replace the desktop app with a web-only app
- Use **PySide6** unless there is a strong reason not to
- Keep JSON as the default local storage backend
- Keep PostgreSQL behind a storage abstraction
- Keep advanced features scaffolded if they cannot be fully implemented in one pass
- Do not hardcode secrets
- Use `.env` or config-driven settings
- Keep modules small and focused
- Do not collapse the app into one file

## Folder intent
- `app/ui/` — desktop interface
- `app/engine/` — workbook and formula logic
- `app/formulas/` — built-in Excel-style functions
- `app/storage/` — JSON and PostgreSQL adapters
- `app/auth/` — login and identity logic
- `app/permissions/` — workbook sharing and access control
- `app/services/` — email and shared services
- `app/models/` — workbook, sheet, cell, formatting, user models
- `server/` — collaboration backend
- `plugins/` — user-defined spreadsheet functions
- `db/` — PostgreSQL schema, setup, migration scripts
- `tests/` — automated tests
- `data/` — sample JSON workbooks and local data files
- `docs/` — project docs and prompt files

## Delivery expectations
When implementing tasks:
1. Preserve the existing architecture unless a change is necessary
2. Prefer completing the current scaffold over redesigning it
3. Mark scaffolded features clearly in code comments and README
4. Keep business logic separate from UI code
5. Keep storage logic separate from UI code
6. Keep auth and authorization separate from UI code

## Spreadsheet requirements
- Support formulas starting with `=`
- Use Excel 365-style function names where practical
- Dynamically load built-in function modules
- Support custom plugin functions from `plugins/`
- Start with a limited function set and extend cleanly

## Compatibility expectations
- Windows
- macOS Sonoma
- Ubuntu 24.04

## MVP expectations
The MVP should include:
- main desktop window
- menu bar
- toolbar or ribbon area
- formula bar
- worksheet grid
- sheet tabs
- status bar
- workbook open/save in JSON
- editable cells
- multiple sheets
- starter formula engine
- `.xlsx` import/export scaffold or working first pass
- placeholder auth/storage/server modules

## Quality expectations
- Production-minded scaffold, not toy code
- Modular files
- Docstrings where useful
- Tests or test scaffolds for core modules
- README kept accurate as implementation evolves
