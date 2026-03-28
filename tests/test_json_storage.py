"""Tests for JSON storage scaffold."""

from __future__ import annotations

import json

import pytest

from app.models.workbook import Workbook
from app.storage.json_storage import JsonWorkbookStorage, StorageValidationError


def test_save_and_load_roundtrip(tmp_path):
    storage = JsonWorkbookStorage()
    workbook = Workbook(
        name="Finance Q1",
        metadata={"owner": "ana@example.com", "tags": ["finance", "quarterly"]},
        permissions={"owner": "ana@example.com", "shared_with": [{"user": "team@example.com", "role": "editor"}]},
    )
    sheet = workbook.add_sheet("Summary")
    a1 = sheet.get_cell("A1")
    a1.value = 1200
    a1.formatting = {"number_format": "currency", "bold": True}

    b1 = sheet.get_cell("B1")
    b1.formula = "=A1*0.1"
    b1.value = 120

    target = tmp_path / "workbook.json"
    storage.save_workbook(str(target), workbook)

    loaded = storage.load_workbook(str(target))

    assert loaded.name == "Finance Q1"
    assert loaded.metadata["owner"] == "ana@example.com"
    assert loaded.permissions["owner"] == "ana@example.com"
    assert loaded.sheets[0].cells["A1"].formatting["number_format"] == "currency"
    assert loaded.sheets[0].cells["B1"].formula == "=A1*0.1"


def test_invalid_active_sheet_index_raises(tmp_path):
    target = tmp_path / "bad_workbook.json"
    target.write_text(
        json.dumps(
            {
                "name": "Bad",
                "active_sheet_index": 3,
                "sheets": [{"name": "Sheet1", "cells": {}}],
            }
        ),
        encoding="utf-8",
    )

    storage = JsonWorkbookStorage()
    with pytest.raises(StorageValidationError):
        storage.load_workbook(str(target))


def test_invalid_sheet_cells_type_raises(tmp_path):
    target = tmp_path / "bad_workbook.json"
    target.write_text(
        json.dumps(
            {
                "name": "Bad",
                "active_sheet_index": 0,
                "sheets": [{"name": "Sheet1", "cells": []}],
            }
        ),
        encoding="utf-8",
    )

    storage = JsonWorkbookStorage()
    with pytest.raises(StorageValidationError):
        storage.load_workbook(str(target))
