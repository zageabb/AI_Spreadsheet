"""PostgreSQL storage adapter scaffold.

Scaffold status:
- Intentionally not implemented in MVP.
- Keep this behind the same storage abstraction as JSON storage.
"""

from __future__ import annotations

from app.models.workbook import Workbook


class PostgresWorkbookStorage:
    """Placeholder PostgreSQL adapter for future milestones."""

    def load_workbook(self, path: str) -> Workbook:  # noqa: ARG002
        raise NotImplementedError("PostgreSQL storage is scaffolded, not yet implemented.")

    def save_workbook(self, path: str, workbook: Workbook) -> None:  # noqa: ARG002
        raise NotImplementedError("PostgreSQL storage is scaffolded, not yet implemented.")
