"""JSON storage adapter for local-first workbook persistence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.workbook import Workbook


_CELL_ADDRESS_PATTERN = re.compile(r"^[A-Z]+[1-9][0-9]*$")


class StorageValidationError(ValueError):
    """Raised when workbook JSON payload is invalid."""


class JsonWorkbookStorage:
    """Serialize/deserialize workbook data as JSON."""

    def load_workbook(self, path: str) -> Workbook:
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StorageValidationError(f"Workbook file was not found: {source}") from exc
        except json.JSONDecodeError as exc:
            raise StorageValidationError(
                f"Workbook JSON is invalid at line {exc.lineno}, column {exc.colno}."
            ) from exc

        self._validate_payload(data)
        return Workbook.from_dict(data)

    def save_workbook(self, path: str, workbook: Workbook) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = workbook.to_dict()
        self._validate_payload(payload)

        temporary_target = target.with_suffix(f"{target.suffix}.tmp")
        temporary_target.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
        temporary_target.replace(target)

    def _validate_payload(self, payload: Any) -> None:
        """Validate workbook JSON schema for reliable persistence."""
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

        schema_version = metadata.get("schema_version") if isinstance(metadata, dict) else None
        if schema_version is not None and not isinstance(schema_version, str):
            raise StorageValidationError("Workbook 'metadata.schema_version' must be a string.")

        permissions = payload.get("permissions", {})
        if permissions is not None and not isinstance(permissions, dict):
            raise StorageValidationError("Workbook 'permissions' must be an object when present.")

        self._validate_permissions(permissions or {})

        for index, sheet in enumerate(sheets):
            self._validate_sheet(sheet, index)

    def _validate_permissions(self, permissions: dict[str, Any]) -> None:
        owner = permissions.get("owner")
        if owner is not None and not isinstance(owner, str):
            raise StorageValidationError("Workbook 'permissions.owner' must be a string or null.")

        shared_with = permissions.get("shared_with", [])
        if not isinstance(shared_with, list):
            raise StorageValidationError("Workbook 'permissions.shared_with' must be a list.")

        for idx, entry in enumerate(shared_with):
            if not isinstance(entry, dict):
                raise StorageValidationError(
                    f"Workbook 'permissions.shared_with[{idx}]' must be an object."
                )
            if not isinstance(entry.get("user"), str) or not entry["user"].strip():
                raise StorageValidationError(
                    f"Workbook 'permissions.shared_with[{idx}].user' must be a non-empty string."
                )
            role = entry.get("role")
            if role is not None and not isinstance(role, str):
                raise StorageValidationError(
                    f"Workbook 'permissions.shared_with[{idx}].role' must be a string when present."
                )

    def _validate_sheet(self, sheet: Any, index: int) -> None:
        if not isinstance(sheet, dict):
            raise StorageValidationError(f"Sheet at index {index} must be an object.")

        sheet_name = sheet.get("name")
        if not isinstance(sheet_name, str) or not sheet_name.strip():
            raise StorageValidationError(f"Sheet at index {index} must have a non-empty 'name'.")

        sheet_metadata = sheet.get("metadata", {})
        if sheet_metadata is not None and not isinstance(sheet_metadata, dict):
            raise StorageValidationError(f"Sheet '{sheet_name}' metadata must be an object when present.")

        cells = sheet.get("cells", {})
        if not isinstance(cells, dict):
            raise StorageValidationError(f"Sheet '{sheet_name}' must contain 'cells' as an object.")

        for address, cell in cells.items():
            self._validate_cell(sheet_name, address, cell)

    def _validate_cell(self, sheet_name: str, address: Any, cell: Any) -> None:
        if not isinstance(address, str) or not _CELL_ADDRESS_PATTERN.match(address.upper()):
            raise StorageValidationError(
                f"Sheet '{sheet_name}' has invalid cell address '{address}'."
            )
        if not isinstance(cell, dict):
            raise StorageValidationError(f"Sheet '{sheet_name}' cell '{address}' must be an object.")

        formula = cell.get("formula")
        if formula is not None:
            if not isinstance(formula, str):
                raise StorageValidationError(
                    f"Sheet '{sheet_name}' cell '{address}' formula must be a string or null."
                )
            if formula and not formula.startswith("="):
                raise StorageValidationError(
                    f"Sheet '{sheet_name}' cell '{address}' formula must start with '='."
                )

        formatting = cell.get("formatting", {})
        if formatting is not None and not isinstance(formatting, dict):
            raise StorageValidationError(
                f"Sheet '{sheet_name}' cell '{address}' has invalid 'formatting'."
            )
