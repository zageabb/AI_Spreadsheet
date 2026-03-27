"""JSON storage adapter for local-first workbook persistence."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.cell import Cell
from app.models.sheet import Worksheet
from app.models.workbook import Workbook


class JsonWorkbookStorage:
    """Serialize/deserialize workbook data as JSON."""

    def load_workbook(self, path: str) -> Workbook:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))

        workbook = Workbook(name=data.get("name", "Untitled"))
        workbook.active_sheet_index = data.get("active_sheet_index", 0)

        for sheet_data in data.get("sheets", []):
            sheet = Worksheet(name=sheet_data["name"])
            for addr, cell_data in sheet_data.get("cells", {}).items():
                sheet.cells[addr] = Cell(
                    address=addr,
                    value=cell_data.get("value"),
                    formula=cell_data.get("formula"),
                    formatting=cell_data.get("formatting", {}),
                )
            workbook.sheets.append(sheet)

        if not workbook.sheets:
            workbook.add_sheet("Sheet1")
        return workbook

    def save_workbook(self, path: str, workbook: Workbook) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "name": workbook.name,
            "active_sheet_index": workbook.active_sheet_index,
            "sheets": [
                {
                    "name": sheet.name,
                    "cells": {
                        addr: {
                            "value": cell.value,
                            "formula": cell.formula,
                            "formatting": cell.formatting,
                        }
                        for addr, cell in sheet.cells.items()
                    },
                }
                for sheet in workbook.sheets
            ],
        }

        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
