"""Verified OOXML package snapshots used as export templates."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook


OOXML_METADATA_KEY = "ooxml_passthrough"


class OOXMLPreservationError(ValueError):
    """Raised when a preserved OOXML package is invalid or unsafe to restore."""


class OOXMLPreservationLayer:
    """Capture an original Office package and restore it as an edit template.

    The snapshot is embedded in workbook metadata so it survives JSON and
    PostgreSQL storage. A checksum prevents silently exporting from damaged or
    modified package data.
    """

    def __init__(self, max_bytes: int | None = None) -> None:
        self.max_bytes = max_bytes if max_bytes is not None else int(
            os.getenv("OOXML_PASSTHROUGH_MAX_BYTES", str(50 * 1024 * 1024))
        )
        if self.max_bytes <= 0:
            raise ValueError("OOXML_PASSTHROUGH_MAX_BYTES must be positive.")

    def capture(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        data = source.read_bytes()
        if len(data) > self.max_bytes:
            raise OOXMLPreservationError(
                f"OOXML package is {len(data)} bytes; passthrough limit is {self.max_bytes} bytes."
            )
        try:
            with ZipFile(io.BytesIO(data)) as package:
                names = set(package.namelist())
                if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                    raise OOXMLPreservationError("File is not a valid Excel OOXML package.")
                expanded_size = sum(item.file_size for item in package.infolist())
                if expanded_size > self.max_bytes * 10:
                    raise OOXMLPreservationError("OOXML package expands beyond the safe passthrough limit.")
                preserved_parts = sum(
                    name.startswith(("xl/charts/", "xl/drawings/", "xl/media/", "xl/embeddings/"))
                    for name in names
                )
        except BadZipFile as exc:
            raise OOXMLPreservationError("File is not a valid OOXML ZIP package.") from exc
        return {
            "schema_version": 1,
            "source_name": source.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "preserved_parts": preserved_parts,
            "package_base64": base64.b64encode(data).decode("ascii"),
        }

    def restore_bytes(self, metadata: dict[str, Any]) -> bytes | None:
        payload = metadata.get(OOXML_METADATA_KEY)
        if not isinstance(payload, dict):
            return None
        try:
            data = base64.b64decode(str(payload["package_base64"]), validate=True)
        except (KeyError, ValueError) as exc:
            raise OOXMLPreservationError("Stored OOXML package data is invalid.") from exc
        if len(data) > self.max_bytes or len(data) != int(payload.get("size", -1)):
            raise OOXMLPreservationError("Stored OOXML package size validation failed.")
        if not hmac.compare_digest(
            hashlib.sha256(data).hexdigest(), str(payload.get("sha256", ""))
        ):
            raise OOXMLPreservationError("Stored OOXML package checksum validation failed.")
        return data

    def open_template(self, metadata: dict[str, Any]):
        data = self.restore_bytes(metadata)
        if data is None:
            return None
        return load_workbook(io.BytesIO(data), data_only=False, keep_vba=True)
