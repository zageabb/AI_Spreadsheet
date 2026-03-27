"""Storage abstraction interfaces."""

from __future__ import annotations

from typing import Protocol

from app.models.workbook import Workbook


class WorkbookStorage(Protocol):
    """Storage protocol for workbook persistence."""

    def load_workbook(self, path: str) -> Workbook:
        """Load a workbook from path."""

    def save_workbook(self, path: str, workbook: Workbook) -> None:
        """Persist a workbook to path."""
