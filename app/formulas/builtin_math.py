"""Built-in Excel-style math and aggregate formula functions for MVP."""

from __future__ import annotations

from math import ceil, floor, isfinite, sqrt
from typing import Any

from app.engine.formula_engine import flatten_args


def _to_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return 0.0
        return float(stripped)
    raise ValueError(f"Unsupported numeric value: {value}")


def SUM(*args: Any) -> float:  # noqa: N802
    values = [_to_number(arg) for arg in flatten_args(args)]
    return float(sum(values))


def AVERAGE(*args: Any) -> float:  # noqa: N802
    values = [_to_number(arg) for arg in flatten_args(args)]
    return float(sum(values) / len(values)) if values else 0.0


def MIN(*args: Any) -> float:  # noqa: N802
    values = [_to_number(arg) for arg in flatten_args(args)]
    return float(min(values)) if values else 0.0


def MAX(*args: Any) -> float:  # noqa: N802
    values = [_to_number(arg) for arg in flatten_args(args)]
    return float(max(values)) if values else 0.0


def COUNT(*args: Any) -> float:  # noqa: N802
    count = 0
    for arg in flatten_args(args):
        if arg is None:
            continue
        if isinstance(arg, str) and arg.strip() == "":
            continue
        if isinstance(arg, (int, float, bool)):
            count += 1
            continue
        if isinstance(arg, str):
            try:
                value = float(arg.strip())
            except ValueError:
                continue
            if isfinite(value):
                count += 1
    return float(count)


def ROUND(number: Any, digits: Any = 0) -> float:  # noqa: N802
    return float(round(_to_number(number), int(_to_number(digits))))


def ABS(number: Any) -> float:  # noqa: N802
    return float(abs(_to_number(number)))


def INT(number: Any) -> float:  # noqa: N802
    return float(floor(_to_number(number)))


def MOD(number: Any, divisor: Any) -> float:  # noqa: N802
    denominator = _to_number(divisor)
    if denominator == 0:
        raise ValueError("#DIV/0!")
    return float(_to_number(number) % denominator)


def POWER(number: Any, power: Any) -> float:  # noqa: N802
    return float(_to_number(number) ** _to_number(power))


def SQRT(number: Any) -> float:  # noqa: N802
    value = _to_number(number)
    if value < 0:
        raise ValueError("#NUM!")
    return float(sqrt(value))


def ROUNDUP(number: Any, digits: Any = 0) -> float:  # noqa: N802
    value=_to_number(number); places=int(_to_number(digits)); factor=10**places
    return float((ceil(abs(value)*factor)/factor) * (-1 if value<0 else 1))


def ROUNDDOWN(number: Any, digits: Any = 0) -> float:  # noqa: N802
    value=_to_number(number); places=int(_to_number(digits)); factor=10**places
    return float((floor(abs(value)*factor)/factor) * (-1 if value<0 else 1))


def CEILING(number: Any, significance: Any = 1) -> float:  # noqa: N802
    value=_to_number(number); step=abs(_to_number(significance))
    if step==0:return 0.0
    return float(ceil(value/step)*step)


def FLOOR(number: Any, significance: Any = 1) -> float:  # noqa: N802
    value=_to_number(number); step=abs(_to_number(significance))
    if step==0:return 0.0
    return float(floor(value/step)*step)


def SUMPRODUCT(*arrays: Any) -> float:  # noqa: N802
    vectors = [flatten_args([array]) for array in arrays]
    if not vectors:
        return 0.0
    if len({len(vector) for vector in vectors}) != 1:
        raise ValueError("#VALUE!")
    return float(sum(
        _to_number(value)
        for value in (product for items in zip(*vectors) for product in [_product(items)])
    ))


def _product(values: tuple[Any, ...]) -> float:
    result = 1.0
    for value in values:
        result *= _to_number(value)
    return result
