"""Built-in Excel-style math formula functions for MVP."""

from __future__ import annotations


def SUM(*args: float) -> float:  # noqa: N802 - Excel-compatible naming
    return float(sum(args))


def AVERAGE(*args: float) -> float:  # noqa: N802
    return float(sum(args) / len(args)) if args else 0.0


def MIN(*args: float) -> float:  # noqa: N802
    return float(min(args)) if args else 0.0


def MAX(*args: float) -> float:  # noqa: N802
    return float(max(args)) if args else 0.0
