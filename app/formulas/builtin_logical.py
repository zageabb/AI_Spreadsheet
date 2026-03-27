"""Built-in Excel-style logical functions for MVP."""

from __future__ import annotations

from typing import Any

from app.engine.formula_engine import flatten_args


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"TRUE", "YES", "Y"}:
            return True
        if normalized in {"FALSE", "NO", "N", ""}:
            return False
        try:
            return float(normalized) != 0
        except ValueError:
            return True
    return bool(value)


def IF(condition: Any, true_value: Any, false_value: Any = False) -> Any:  # noqa: N802
    return true_value if _to_bool(condition) else false_value


def AND(*args: Any) -> bool:  # noqa: N802
    values = flatten_args(args)
    return all(_to_bool(value) for value in values) if values else True


def OR(*args: Any) -> bool:  # noqa: N802
    return any(_to_bool(value) for value in flatten_args(args))


def NOT(value: Any) -> bool:  # noqa: N802
    return not _to_bool(value)
