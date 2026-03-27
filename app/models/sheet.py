"""Worksheet model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.cell import Cell


@dataclass(slots=True)
class Worksheet:
    """Represents a worksheet in a workbook."""

    name: str
    cells: dict[str, Cell] = field(default_factory=dict)

    def get_cell(self, address: str) -> Cell:
        """Get a cell by address, creating it if it does not exist."""
        if address not in self.cells:
            self.cells[address] = Cell(address=address)
        return self.cells[address]
