"""Common Excel-style statistical functions."""

from math import sqrt
from statistics import median
from typing import Any

from app.engine.formula_engine import flatten_args


def _numbers(args) -> list[float]:
    result=[]
    for value in flatten_args(args):
        if isinstance(value,bool):result.append(float(value))
        elif isinstance(value,(int,float)):result.append(float(value))
        elif isinstance(value,str):
            try:result.append(float(value.strip()))
            except ValueError:pass
    return result


def MEDIAN(*args: Any) -> float:  # noqa: N802
    values=_numbers(args)
    if not values:raise ValueError("#NUM!")
    return float(median(values))


def PRODUCT(*args: Any) -> float:  # noqa: N802
    result=1.0
    for value in _numbers(args):result*=value
    return result


def STDEV_S(*args: Any) -> float:  # noqa: N802
    values=_numbers(args)
    if len(values)<2:raise ValueError("#DIV/0!")
    mean=sum(values)/len(values)
    return sqrt(sum((value-mean)**2 for value in values)/(len(values)-1))


def STDEV_P(*args: Any) -> float:  # noqa: N802
    values=_numbers(args)
    if not values:raise ValueError("#DIV/0!")
    mean=sum(values)/len(values)
    return sqrt(sum((value-mean)**2 for value in values)/len(values))


def VAR_S(*args: Any) -> float:  # noqa: N802
    return STDEV_S(*args)**2


def VAR_P(*args: Any) -> float:  # noqa: N802
    return STDEV_P(*args)**2


def LARGE(array: Any, k: Any) -> float:  # noqa: N802
    values=sorted(_numbers([array]),reverse=True); index=int(float(k))-1
    if index<0 or index>=len(values):raise ValueError("#NUM!")
    return values[index]


def SMALL(array: Any, k: Any) -> float:  # noqa: N802
    values=sorted(_numbers([array])); index=int(float(k))-1
    if index<0 or index>=len(values):raise ValueError("#NUM!")
    return values[index]


def RANK_EQ(number: Any, ref: Any, order: Any = 0) -> float:  # noqa: N802
    value=float(number); values=sorted(_numbers([ref]),reverse=not bool(order))
    try:return float(values.index(value)+1)
    except ValueError as exc:raise ValueError("#N/A") from exc
