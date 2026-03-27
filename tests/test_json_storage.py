"""Tests for JSON storage scaffold."""

from __future__ import annotations

from app.models.workbook import Workbook
from app.storage.json_storage import JsonWorkbookStorage


def test_save_and_load_roundtrip(tmp_path):
    storage = JsonWorkbookStorage()
    workbook = Workbook(name="Test")
    sheet = workbook.add_sheet("Sheet1")
    sheet.get_cell("A1").value = "hello"

    target = tmp_path / "workbook.json"
    storage.save_workbook(str(target), workbook)

    loaded = storage.load_workbook(str(target))

    assert loaded.name == "Test"
    assert loaded.sheets[0].cells["A1"].value == "hello"
