"""Excel-style coordinates without UI size assumptions."""

from __future__ import annotations

from dataclasses import dataclass
import re

_CELL_RE = re.compile(r"^(?:(?P<sheet>'(?:[^']|'')+'|[^!]+)!)?(?P<col_abs>\$?)(?P<col>[A-Za-z]+)(?P<row_abs>\$?)(?P<row>[1-9]\d*)$")


def column_index_to_label(index: int) -> str:
    """Convert a zero-based column index to A, Z, AA ... XFD."""
    if index < 0:
        raise ValueError("Column index must be non-negative")
    label = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


def column_label_to_index(label: str) -> int:
    """Convert A, Z, AA ... to a zero-based column index."""
    text = label.strip().upper()
    if not text or not text.isalpha():
        raise ValueError(f"Invalid column label: {label!r}")
    value = 0
    for char in text:
        value = value * 26 + ord(char) - 64
    return value - 1


@dataclass(frozen=True, slots=True)
class CellAddress:
    row: int
    column: int
    sheet: str | None = None
    absolute_row: bool = False
    absolute_column: bool = False

    @classmethod
    def parse(cls, value: str) -> "CellAddress":
        match = _CELL_RE.match(value.strip())
        if not match:
            raise ValueError(f"Invalid cell address: {value!r}")
        sheet = match.group("sheet")
        if sheet and sheet.startswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
        return cls(
            row=int(match.group("row")) - 1,
            column=column_label_to_index(match.group("col")),
            sheet=sheet,
            absolute_row=bool(match.group("row_abs")),
            absolute_column=bool(match.group("col_abs")),
        )

    def a1(self, include_sheet: bool = True) -> str:
        col = ("$" if self.absolute_column else "") + column_index_to_label(self.column)
        row = ("$" if self.absolute_row else "") + str(self.row + 1)
        if not include_sheet or self.sheet is None:
            return col + row
        sheet = self.sheet if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", self.sheet) else "'" + self.sheet.replace("'", "''") + "'"
        return f"{sheet}!{col}{row}"


@dataclass(frozen=True, slots=True)
class CellRange:
    start: CellAddress
    end: CellAddress

    @classmethod
    def parse(cls, value: str) -> "CellRange":
        left, separator, right = value.partition(":")
        start = CellAddress.parse(left)
        end = CellAddress.parse(right) if separator else start
        if end.sheet is None and start.sheet is not None:
            end = CellAddress(end.row, end.column, start.sheet, end.absolute_row, end.absolute_column)
        if start.sheet != end.sheet:
            raise ValueError("A range cannot span worksheets")
        return cls(start, end)

    def addresses(self):
        top, bottom = sorted((self.start.row, self.end.row))
        left, right = sorted((self.start.column, self.end.column))
        for row in range(top, bottom + 1):
            for column in range(left, right + 1):
                yield CellAddress(row, column, self.start.sheet)
