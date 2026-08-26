"""Conditional aggregate functions used by analytical workbooks."""

from __future__ import annotations

import operator
import re
from typing import Any

from app.engine.formula_engine import flatten_args


def COUNTA(*args: Any) -> float:  # noqa: N802
    return float(sum(value not in (None, "") for value in flatten_args(args)))


def COUNTIF(cell_range: Any, criteria: Any) -> float:  # noqa: N802
    predicate = _criteria(criteria)
    return float(sum(predicate(value) for value in flatten_args([cell_range])))


def SUMIF(cell_range: Any, criteria: Any, sum_range: Any = None) -> float:  # noqa: N802
    source = flatten_args([cell_range])
    target = source if sum_range is None else flatten_args([sum_range])
    if len(source) != len(target):
        raise ValueError("#VALUE!")
    predicate = _criteria(criteria)
    return float(sum(float(value or 0) for item, value in zip(source, target) if predicate(item)))


def AVERAGEIF(cell_range: Any, criteria: Any, average_range: Any = None) -> float:  # noqa: N802
    source = flatten_args([cell_range])
    target = source if average_range is None else flatten_args([average_range])
    if len(source) != len(target):
        raise ValueError("#VALUE!")
    predicate = _criteria(criteria)
    values = [float(value) for item, value in zip(source, target) if predicate(item) and value not in (None, "")]
    if not values:
        raise ValueError("#DIV/0!")
    return float(sum(values) / len(values))


def _criteria(criteria: Any):
    if not isinstance(criteria, str):
        return lambda value: value == criteria
    match = re.match(r"^(<=|>=|<>|=|<|>)(.*)$", criteria)
    if match:
        operation, expected = match.groups()
        functions = {"<": operator.lt, ">": operator.gt, "<=": operator.le,
                     ">=": operator.ge, "=": operator.eq, "<>": operator.ne}
        expected = _scalar(expected)
        return lambda value: _safe_compare(functions[operation], value, expected)
    if "*" in criteria or "?" in criteria:
        pattern = re.escape(criteria).replace(r"\*", ".*").replace(r"\?", ".")
        return lambda value: re.fullmatch(pattern, str(value), flags=re.IGNORECASE) is not None
    return lambda value: str(value).casefold() == criteria.casefold()


def _scalar(value: str):
    try:
        return float(value)
    except ValueError:
        return value


def _safe_compare(fn, left, right):
    try:
        return fn(float(left), float(right))
    except (TypeError, ValueError):
        try:
            return fn(str(left).casefold(), str(right).casefold())
        except TypeError:
            return False
