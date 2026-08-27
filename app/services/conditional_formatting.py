"""Portable conditional-format rule evaluation for the desktop grid."""

from __future__ import annotations

from typing import Any

from app.core.coordinates import CellAddress
from app.models.sheet import Worksheet


def formatting_for(sheet: Worksheet, address: str, value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    target = CellAddress.parse(address)
    for rule in sheet.metadata.get("conditional_formats", []):
        if not isinstance(rule, dict) or not _contains(str(rule.get("range", "")), target):
            continue
        if _matches(rule, value):
            for key in ("fill_color", "font_color", "bold"):
                if rule.get(key) is not None:
                    result[key] = rule[key]
    return result


def _contains(range_text: str, target: CellAddress) -> bool:
    for part in range_text.split():
        try:
            if ":" in part:
                start, end = part.split(":", 1)
            else:
                start = end = part
            first, last = CellAddress.parse(start), CellAddress.parse(end)
            if (min(first.row,last.row) <= target.row <= max(first.row,last.row)
                    and min(first.column,last.column) <= target.column <= max(first.column,last.column)):
                return True
        except ValueError:
            continue
    return False


def _matches(rule: dict[str, Any], value: Any) -> bool:
    formulas = rule.get("formula", [])
    if not formulas:
        return False
    first = _scalar(formulas[0])
    operator = str(rule.get("operator") or "equal")
    try:
        if operator == "equal": return value == first
        if operator == "notEqual": return value != first
        if operator == "greaterThan": return value > first
        if operator == "greaterThanOrEqual": return value >= first
        if operator == "lessThan": return value < first
        if operator == "lessThanOrEqual": return value <= first
        if operator == "between" and len(formulas) > 1:return _scalar(formulas[0]) <= value <= _scalar(formulas[1])
        if operator == "notBetween" and len(formulas) > 1:return not (_scalar(formulas[0]) <= value <= _scalar(formulas[1]))
        if operator == "containsText": return str(first).casefold() in str(value).casefold()
    except TypeError:
        return False
    return False


def _scalar(value: Any) -> Any:
    text = str(value)
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    try:return int(text)
    except ValueError:
        try:return float(text)
        except ValueError:return text
