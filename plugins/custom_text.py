"""Example custom plugin formulas loaded from plugins/."""

from __future__ import annotations


def CONCAT(*parts: object) -> str:  # noqa: N802
    return "".join(str(part) for part in parts)
