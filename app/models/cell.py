"""Cell model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


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
    formatting: Dict[str, Any] = field(default_factory=dict)
