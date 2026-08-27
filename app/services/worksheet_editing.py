"""Reversible, UI-independent worksheet editing operations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any, Iterable

from app.core.coordinates import CellAddress
from app.models.cell import Cell
from app.models.sheet import Worksheet


@dataclass(frozen=True, slots=True)
class CellRange:
    top: int
    left: int
    bottom: int
    right: int

    def addresses(self) -> Iterable[str]:
        for row in range(self.top, self.bottom + 1):
            for column in range(self.left, self.right + 1):
                yield CellAddress(row, column).a1(False)


def snapshot(sheet: Worksheet) -> dict[str, Any]:
    """Capture the mutable worksheet state used by an undo command."""
    return {"cells": deepcopy(sheet.cells), "metadata": deepcopy(sheet.metadata)}


def restore(sheet: Worksheet, state: dict[str, Any]) -> None:
    sheet.cells = deepcopy(state["cells"])
    sheet.metadata = deepcopy(state["metadata"])


def clear_cells(sheet: Worksheet, cell_range: CellRange) -> int:
    changed = 0
    for address in cell_range.addresses():
        if address in sheet.cells:
            del sheet.cells[address]
            changed += 1
    return changed


def apply_format(sheet: Worksheet, cell_range: CellRange, updates: dict[str, Any]) -> int:
    changed = 0
    for address in cell_range.addresses():
        cell = sheet.get_cell(address)
        for key, value in updates.items():
            if value is None:
                cell.formatting.pop(key, None)
            else:
                cell.formatting[key] = value
        changed += 1
    return changed


def replace_text(
    sheet: Worksheet, find: str, replacement: str, *, match_case: bool = False,
    cell_range: CellRange | None = None,
) -> int:
    if not find:
        return 0
    addresses = list(cell_range.addresses()) if cell_range else list(sheet.cells)
    flags = 0 if match_case else re.IGNORECASE
    pattern = re.compile(re.escape(find), flags)
    changed = 0
    for address in addresses:
        cell = sheet.cells.get(address)
        if cell is None:
            continue
        source = cell.formula if cell.formula is not None else cell.value
        if not isinstance(source, str):
            continue
        result, count = pattern.subn(replacement, source)
        if not count:
            continue
        if cell.formula is not None:
            cell.formula = result
        else:
            cell.value = result
        changed += 1
    return changed


def insert_rows(sheet: Worksheet, start: int, count: int = 1) -> None:
    _shift_cells(sheet, axis="row", start=start, count=count)


def delete_rows(sheet: Worksheet, start: int, count: int = 1) -> None:
    _delete_and_shift(sheet, axis="row", start=start, count=count)


def insert_columns(sheet: Worksheet, start: int, count: int = 1) -> None:
    _shift_cells(sheet, axis="column", start=start, count=count)


def delete_columns(sheet: Worksheet, start: int, count: int = 1) -> None:
    _delete_and_shift(sheet, axis="column", start=start, count=count)


def sort_rows(sheet: Worksheet, cell_range: CellRange, key_column: int, *, reverse: bool = False) -> None:
    """Sort whole rows inside a rectangular range while keeping cell payloads intact."""
    rows: list[list[Cell | None]] = []
    for row in range(cell_range.top, cell_range.bottom + 1):
        rows.append([
            deepcopy(sheet.cells.get(CellAddress(row, column).a1(False)))
            for column in range(cell_range.left, cell_range.right + 1)
        ])
    offset = key_column - cell_range.left

    def key(row: list[Cell | None]):
        cell = row[offset]
        value = None if cell is None else cell.value
        return (value is None, type(value).__name__, str(value).casefold() if isinstance(value, str) else value)

    try:
        rows.sort(key=key, reverse=reverse)
    except TypeError:
        rows.sort(key=lambda row: str(key(row)), reverse=reverse)
    clear_cells(sheet, cell_range)
    for row_offset, cells in enumerate(rows):
        for column_offset, cell in enumerate(cells):
            if cell is None:
                continue
            address = CellAddress(cell_range.top + row_offset, cell_range.left + column_offset).a1(False)
            cell.address = address
            sheet.cells[address] = cell


def _shift_cells(sheet: Worksheet, *, axis: str, start: int, count: int) -> None:
    if count < 1:
        raise ValueError("count must be positive")
    moved: dict[str, Cell] = {}
    for address, cell in sheet.cells.items():
        parsed = CellAddress.parse(address)
        row, column = parsed.row, parsed.column
        coordinate = row if axis == "row" else column
        if coordinate >= start:
            if axis == "row": row += count
            else: column += count
        new_address = CellAddress(row, column).a1(False)
        clone = deepcopy(cell); clone.address = new_address; moved[new_address] = clone
    sheet.cells = moved
    _rewrite_formula_references(sheet, axis=axis, start=start, count=count, deleting=False)


def _delete_and_shift(sheet: Worksheet, *, axis: str, start: int, count: int) -> None:
    if count < 1:
        raise ValueError("count must be positive")
    end = start + count
    moved: dict[str, Cell] = {}
    for address, cell in sheet.cells.items():
        parsed = CellAddress.parse(address)
        row, column = parsed.row, parsed.column
        coordinate = row if axis == "row" else column
        if start <= coordinate < end:
            continue
        if coordinate >= end:
            if axis == "row": row -= count
            else: column -= count
        new_address = CellAddress(row, column).a1(False)
        clone = deepcopy(cell); clone.address = new_address; moved[new_address] = clone
    sheet.cells = moved
    _rewrite_formula_references(sheet, axis=axis, start=start, count=count, deleting=True)


_LOCAL_REFERENCE = re.compile(r"(?<![A-Z0-9_!])(\$?)([A-Z]{1,3})(\$?)([1-9][0-9]*)", re.IGNORECASE)


def _rewrite_formula_references(
    sheet: Worksheet, *, axis: str, start: int, count: int, deleting: bool,
) -> None:
    """Move unqualified A1 references after structural row/column edits."""
    end = start + count

    def replace(match: re.Match[str]) -> str:
        address = CellAddress.parse(f"{match.group(2)}{match.group(4)}")
        coordinate = address.row if axis == "row" else address.column
        if deleting and start <= coordinate < end:
            return "#REF!"
        if coordinate >= (end if deleting else start):
            coordinate += -count if deleting else count
        row = coordinate if axis == "row" else address.row
        column = address.column if axis == "row" else coordinate
        shifted = CellAddress(row, column).a1(False)
        column_label = re.match(r"[A-Z]+", shifted).group(0)
        row_label = shifted[len(column_label):]
        return f"{match.group(1)}{column_label}{match.group(3)}{row_label}"

    for cell in sheet.cells.values():
        if cell.formula:
            cell.formula = _LOCAL_REFERENCE.sub(replace, cell.formula)
