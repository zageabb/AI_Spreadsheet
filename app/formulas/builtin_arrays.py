"""Excel 365-style dynamic-array functions."""

from __future__ import annotations

from typing import Any

from app.engine.formula_engine import FormulaEvaluationError, RangeValue, flatten_args


def SEQUENCE(rows: Any, columns: Any = 1, start: Any = 1, step: Any = 1) -> RangeValue:  # noqa: N802
    row_count = int(float(rows))
    column_count = int(float(columns))
    if row_count < 1 or column_count < 1:
        raise FormulaEvaluationError("#CALC!", "SEQUENCE dimensions must be positive")
    first = float(start)
    increment = float(step)
    values = [first + increment * index for index in range(row_count * column_count)]
    return RangeValue([
        values[index:index + column_count]
        for index in range(0, len(values), column_count)
    ])


def FILTER(array: Any, include: Any, if_empty: Any = None) -> RangeValue:  # noqa: N802
    rows = _matrix(array)
    mask = flatten_args([include])
    if len(mask) != len(rows):
        raise FormulaEvaluationError("#VALUE!", "FILTER mask must match the row count")
    filtered = [row for row, keep in zip(rows, mask) if bool(keep)]
    if filtered:
        return RangeValue(filtered)
    if if_empty is None:
        raise FormulaEvaluationError("#CALC!", "FILTER returned no rows")
    return RangeValue([[if_empty]])


def SORT(array: Any, sort_index: Any = 1, sort_order: Any = 1) -> RangeValue:  # noqa: N802
    rows = _matrix(array)
    column = int(float(sort_index)) - 1
    if column < 0 or any(column >= len(row) for row in rows):
        raise FormulaEvaluationError("#VALUE!", "SORT column is outside the array")
    descending = int(float(sort_order)) == -1
    try:
        return RangeValue(sorted(rows, key=lambda row: (row[column] is None, row[column]), reverse=descending))
    except TypeError:
        return RangeValue(sorted(rows, key=lambda row: str(row[column]), reverse=descending))


def UNIQUE(array: Any) -> RangeValue:  # noqa: N802
    rows = _matrix(array)
    unique_rows: list[list[Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        marker = tuple(repr(value) for value in row)
        if marker not in seen:
            seen.add(marker)
            unique_rows.append(row)
    return RangeValue(unique_rows)


def _matrix(value: Any) -> list[list[Any]]:
    if isinstance(value, RangeValue):
        return [list(row) for row in value]
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (list, tuple)):
            return [list(row) for row in value]
        return [[item] for item in value]
    return [[value]]
