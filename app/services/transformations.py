"""Recorded, deterministic worksheet transformations (Power Query-style MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.coordinates import CellAddress, column_index_to_label
from app.models.sheet import Worksheet


@dataclass(slots=True)
class TransformationStep:
    operation: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"operation": self.operation, "parameters": self.parameters}


class TransformationPipeline:
    """Apply reviewable transformation steps to row dictionaries."""

    def __init__(self, steps: list[TransformationStep] | None = None) -> None:
        self.steps = steps or []

    def apply(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = [dict(row) for row in rows]
        for step in self.steps:
            method = getattr(self, f"_apply_{step.operation}", None)
            if method is None:
                raise ValueError(f"Unsupported transformation: {step.operation}")
            result = method(result, step.parameters)
        return result

    @staticmethod
    def _apply_select(rows, params):
        columns = params["columns"]
        return [{column: row.get(column) for column in columns} for row in rows]

    @staticmethod
    def _apply_rename(rows, params):
        mapping = params["mapping"]
        return [{mapping.get(key, key): value for key, value in row.items()} for row in rows]

    @staticmethod
    def _apply_filter(rows, params):
        column, operator, expected = params["column"], params.get("operator", "eq"), params.get("value")
        operations = {"eq": lambda a: a == expected, "ne": lambda a: a != expected,
                      "contains": lambda a: str(expected).lower() in str(a).lower(),
                      "gt": lambda a: a is not None and a > expected, "lt": lambda a: a is not None and a < expected}
        if operator not in operations:
            raise ValueError(f"Unsupported filter operator: {operator}")
        return [row for row in rows if operations[operator](row.get(column))]

    @staticmethod
    def _apply_sort(rows, params):
        column = params["column"]
        return sorted(rows, key=lambda row: (row.get(column) is None, row.get(column)), reverse=bool(params.get("descending")))

    @staticmethod
    def _apply_fill_null(rows, params):
        column, value = params["column"], params.get("value")
        return [{**row, column: value if row.get(column) is None else row.get(column)} for row in rows]


def worksheet_to_rows(sheet: Worksheet, header_row: int = 0) -> list[dict[str, Any]]:
    """Convert a sparse worksheet region into dictionaries using its header row."""
    occupied = [CellAddress.parse(address) for address in sheet.cells]
    if not occupied:
        return []
    max_column = max(item.column for item in occupied)
    max_row = max(item.row for item in occupied)
    headers = []
    for column in range(max_column + 1):
        cell = sheet.cells.get(f"{column_index_to_label(column)}{header_row + 1}")
        headers.append(str(cell.value) if cell and cell.value not in (None, "") else f"Column{column + 1}")
    rows = []
    for row in range(header_row + 1, max_row + 1):
        record = {}
        for column, header in enumerate(headers):
            cell = sheet.cells.get(f"{column_index_to_label(column)}{row + 1}")
            record[header] = cell.value if cell else None
        rows.append(record)
    return rows
