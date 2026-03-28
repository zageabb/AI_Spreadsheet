"""JSON storage adapter for local-first workbook persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.workbook import Workbook


class StorageValidationError(ValueError):
    """Raised when workbook JSON payload is invalid."""


class JsonWorkbookStorage:
    """Serialize/deserialize workbook data as JSON."""

    def load_workbook(self, path: str) -> Workbook:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        self._validate_payload(data)
        return Workbook.from_dict(data)

    def save_workbook(self, path: str, workbook: Workbook) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = workbook.to_dict()
        self._validate_payload(payload)
        target.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    def _validate_payload(self, payload: Any) -> None:
        """Validate minimal workbook JSON schema for reliable persistence."""
        if not isinstance(payload, dict):
            raise StorageValidationError("Workbook payload must be a JSON object.")

        if not isinstance(payload.get("name"), str) or not payload.get("name", "").strip():
            raise StorageValidationError("Workbook 'name' must be a non-empty string.")

        sheets = payload.get("sheets")
        if not isinstance(sheets, list) or not sheets:
            raise StorageValidationError("Workbook 'sheets' must be a non-empty list.")

        active_index = payload.get("active_sheet_index", 0)
        if not isinstance(active_index, int):
            raise StorageValidationError("Workbook 'active_sheet_index' must be an integer.")

        if active_index < 0 or active_index >= len(sheets):
            raise StorageValidationError("Workbook 'active_sheet_index' is out of range for 'sheets'.")

        metadata = payload.get("metadata", {})
        if metadata is not None and not isinstance(metadata, dict):
            raise StorageValidationError("Workbook 'metadata' must be an object when present.")

        permissions = payload.get("permissions", {})
        if permissions is not None and not isinstance(permissions, dict):
            raise StorageValidationError("Workbook 'permissions' must be an object when present.")

        for index, sheet in enumerate(sheets):
            if not isinstance(sheet, dict):
                raise StorageValidationError(f"Sheet at index {index} must be an object.")

            sheet_name = sheet.get("name")
            if not isinstance(sheet_name, str) or not sheet_name.strip():
                raise StorageValidationError(f"Sheet at index {index} must have a non-empty 'name'.")

            cells = sheet.get("cells", {})
            if not isinstance(cells, dict):
                raise StorageValidationError(f"Sheet '{sheet_name}' must contain 'cells' as an object.")

            for address, cell in cells.items():
                if not isinstance(address, str) or not address.strip():
                    raise StorageValidationError(f"Sheet '{sheet_name}' has invalid cell address key.")
                if not isinstance(cell, dict):
                    raise StorageValidationError(
                        f"Sheet '{sheet_name}' cell '{address}' must be an object."
                    )

                formatting = cell.get("formatting", {})
                if formatting is not None and not isinstance(formatting, dict):
                    raise StorageValidationError(
                        f"Sheet '{sheet_name}' cell '{address}' has invalid 'formatting'."
                    )
