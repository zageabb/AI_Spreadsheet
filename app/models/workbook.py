"""Workbook model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.sheet import Worksheet


@dataclass(slots=True)
class Workbook:
    """Represents a workbook with one or more worksheets."""

    name: str = "Untitled"
    sheets: list[Worksheet] = field(default_factory=list)
    active_sheet_index: int = 0

    def get_active_sheet(self) -> Worksheet:
        """Return the active worksheet, ensuring one exists."""
        if not self.sheets:
            self.sheets.append(Worksheet(name="Sheet1"))
        return self.sheets[self.active_sheet_index]

    def add_sheet(self, name: str | None = None) -> Worksheet:
        """Add and return a worksheet."""
        sheet_name = name or f"Sheet{len(self.sheets) + 1}"
        sheet = Worksheet(name=sheet_name)
        self.sheets.append(sheet)
        return sheet
