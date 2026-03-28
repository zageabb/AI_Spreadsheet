"""Workbook model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models.sheet import Worksheet


WORKBOOK_SCHEMA_VERSION = "1.1"
DEFAULT_PERMISSIONS = {
    "owner": None,
    "shared_with": [],
}


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp suitable for metadata fields."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Workbook:
    """Represents a workbook with one or more worksheets."""

    name: str = "Untitled"
    sheets: list[Worksheet] = field(default_factory=list)
    active_sheet_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)

    def get_active_sheet(self) -> Worksheet:
        """Return the active worksheet, ensuring one exists."""
        if not self.sheets:
            self.sheets.append(Worksheet(name="Sheet1"))
        self.active_sheet_index = max(0, min(self.active_sheet_index, len(self.sheets) - 1))
        return self.sheets[self.active_sheet_index]

    def add_sheet(self, name: str | None = None) -> Worksheet:
        """Add and return a worksheet."""
        sheet_name = name or f"Sheet{len(self.sheets) + 1}"
        sheet = Worksheet(name=sheet_name)
        self.sheets.append(sheet)
        return sheet

    def to_dict(self) -> dict[str, Any]:
        """Return the workbook as a JSON-serializable dictionary."""
        now = _utc_timestamp()

        metadata = {
            "schema_version": WORKBOOK_SCHEMA_VERSION,
            "created_at": self.metadata.get("created_at", now),
            "updated_at": now,
            **self.metadata,
        }

        permissions = {
            **DEFAULT_PERMISSIONS,
            **self.permissions,
        }

        if not self.sheets:
            self.add_sheet("Sheet1")

        self.active_sheet_index = max(0, min(self.active_sheet_index, len(self.sheets) - 1))

        return {
            "name": self.name,
            "active_sheet_index": self.active_sheet_index,
            "metadata": metadata,
            "permissions": permissions,
            "sheets": [sheet.to_dict() for sheet in self.sheets],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Workbook":
        """Create a workbook from a JSON dictionary payload."""
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        permissions = payload.get("permissions", {})
        if not isinstance(permissions, dict):
            permissions = {}

        try:
            active_sheet_index = int(payload.get("active_sheet_index", 0) or 0)
        except (TypeError, ValueError):
            active_sheet_index = 0

        workbook = cls(
            name=str(payload.get("name") or "Untitled"),
            active_sheet_index=active_sheet_index,
            metadata=metadata,
            permissions={**DEFAULT_PERMISSIONS, **permissions},
        )

        raw_sheets = payload.get("sheets", [])
        if isinstance(raw_sheets, list):
            for sheet_payload in raw_sheets:
                if isinstance(sheet_payload, dict):
                    workbook.sheets.append(Worksheet.from_dict(sheet_payload))

        if not workbook.sheets:
            workbook.add_sheet("Sheet1")

        workbook.active_sheet_index = max(0, min(workbook.active_sheet_index, len(workbook.sheets) - 1))
        return workbook
