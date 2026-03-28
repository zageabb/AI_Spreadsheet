"""Cell model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Cell:
    """Represents an individual worksheet cell.

    Notes:
        This model intentionally keeps formatting minimal in MVP and is designed
        to be extended in later milestones.
    """

    address: str
    value: Any = None
    formula: str | None = None
    formatting: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this cell."""
        return {
            "value": self.value,
            "formula": self.formula,
            "formatting": dict(self.formatting),
        }

    @classmethod
    def from_dict(cls, address: str, payload: dict[str, Any]) -> "Cell":
        """Build a cell from JSON payload data."""
        formatting = payload.get("formatting", {})
        if not isinstance(formatting, dict):
            formatting = {}

        formula = payload.get("formula")
        if formula is not None and not isinstance(formula, str):
            formula = str(formula)

        return cls(
            address=address,
            value=payload.get("value"),
            formula=formula,
            formatting=formatting,
        )
