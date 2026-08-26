"""Storage adapter exports and backend selection helpers."""

from __future__ import annotations

import os

from app.storage.base import WorkbookStorage
from app.storage.json_storage import JsonWorkbookStorage


def get_workbook_storage() -> WorkbookStorage:
    """Return configured workbook storage adapter.

    Storage is selected through `STORAGE_BACKEND` env var.
    - `json` (default)
    - `postgres`
    """

    backend = os.getenv("STORAGE_BACKEND", "json").strip().lower()
    if backend == "postgres":
        from app.storage.postgres_storage import PostgresWorkbookStorage

        return PostgresWorkbookStorage()
    if backend == "json":
        return JsonWorkbookStorage()
    raise ValueError("STORAGE_BACKEND must be either 'json' or 'postgres'.")


__all__ = [
    "WorkbookStorage",
    "JsonWorkbookStorage",
    "get_workbook_storage",
]
