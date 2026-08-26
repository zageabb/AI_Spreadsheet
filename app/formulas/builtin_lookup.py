"""Common Excel-style lookup and reference functions."""

from __future__ import annotations

from typing import Any

from app.engine.formula_engine import RangeValue, flatten_args


def _vector(value: Any) -> list[Any]:
    return flatten_args([value]) if isinstance(value, (list, tuple)) else [value]


def _matrix(value: Any) -> list[list[Any]]:
    if isinstance(value, RangeValue):
        return [list(row) for row in value]
    if isinstance(value, list) and value and isinstance(value[0], (list, tuple)):
        return [list(row) for row in value]
    if isinstance(value, (list, tuple)):
        return [list(value)]
    return [[value]]


def MATCH(lookup_value: Any, lookup_array: Any, match_type: Any = 0) -> float:  # noqa: N802
    values = _vector(lookup_array)
    mode = int(float(match_type))
    if mode == 0:
        for index, value in enumerate(values, start=1):
            if value == lookup_value or str(value).casefold() == str(lookup_value).casefold():
                return float(index)
        raise ValueError("#N/A")
    candidates = [(index, value) for index, value in enumerate(values, start=1)
                  if (mode > 0 and value <= lookup_value) or (mode < 0 and value >= lookup_value)]
    if not candidates:
        raise ValueError("#N/A")
    return float(candidates[-1][0])


def INDEX(array: Any, row_num: Any, column_num: Any = 1) -> Any:  # noqa: N802
    matrix = _matrix(array)
    row, column = int(float(row_num)) - 1, int(float(column_num)) - 1
    if row < 0 or column < 0 or row >= len(matrix) or column >= len(matrix[row]):
        raise ValueError("#REF!")
    return matrix[row][column]


def XLOOKUP(lookup_value: Any, lookup_array: Any, return_array: Any,
            if_not_found: Any = "#N/A", match_mode: Any = 0) -> Any:  # noqa: N802
    lookups, returns = _vector(lookup_array), _vector(return_array)
    if len(lookups) != len(returns):
        raise ValueError("#VALUE!")
    mode = int(float(match_mode))
    for index, value in enumerate(lookups):
        if (mode == 0 and (value == lookup_value or str(value).casefold() == str(lookup_value).casefold())) \
                or (mode == 2 and _wildcard_match(str(value), str(lookup_value))):
            return returns[index]
    return if_not_found


def VLOOKUP(lookup_value: Any, table_array: Any, col_index_num: Any,
            range_lookup: Any = False) -> Any:  # noqa: N802
    matrix = _matrix(table_array)
    column = int(float(col_index_num)) - 1
    if column < 0 or any(column >= len(row) for row in matrix):
        raise ValueError("#REF!")
    exact = not bool(range_lookup)
    match = None
    for row in matrix:
        if row[0] == lookup_value or str(row[0]).casefold() == str(lookup_value).casefold():
            return row[column]
        if not exact:
            try:
                if row[0] <= lookup_value:
                    match = row[column]
            except TypeError:
                continue
    if match is not None:
        return match
    raise ValueError("#N/A")


def HLOOKUP(lookup_value: Any, table_array: Any, row_index_num: Any,
            range_lookup: Any = False) -> Any:  # noqa: N802
    matrix = _matrix(table_array)
    row_index = int(float(row_index_num)) - 1
    if not matrix or row_index < 0 or row_index >= len(matrix):
        raise ValueError("#REF!")
    column = int(MATCH(lookup_value, matrix[0], 0 if not range_lookup else 1)) - 1
    return matrix[row_index][column]


def _wildcard_match(value: str, pattern: str) -> bool:
    import re
    escaped = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(escaped, value, flags=re.IGNORECASE) is not None
