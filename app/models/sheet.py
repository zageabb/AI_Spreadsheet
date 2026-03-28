"""Worksheet model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.cell import Cell


@dataclass(slots=True)
class Worksheet:
    """Represents a worksheet in a workbook."""

    name: str
    cells: dict[str, Cell] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_cell(self, address: str) -> Cell:
        """Get a cell by address, creating it if it does not exist."""
        normalized = address.upper()
        if normalized not in self.cells:
            self.cells[normalized] = Cell(address=normalized)
        return self.cells[normalized]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this worksheet."""
        return {
            "name": self.name,
            "metadata": dict(self.metadata),
            "cells": {addr: cell.to_dict() for addr, cell in sorted(self.cells.items())},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Worksheet":
        """Build a worksheet from JSON payload data."""
        sheet = cls(
            name=str(payload.get("name") or "Sheet"),
            metadata=payload.get("metadata", {}) if isinstance(payload.get("metadata", {}), dict) else {},
        )

        raw_cells = payload.get("cells", {})
        if isinstance(raw_cells, dict):
            for addr, cell_payload in raw_cells.items():
                if not isinstance(cell_payload, dict):
                    continue
                normalized = str(addr).upper()
                sheet.cells[normalized] = Cell.from_dict(normalized, cell_payload)

        return sheet
