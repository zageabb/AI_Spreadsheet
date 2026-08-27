"""Tests for workbook model serialization defaults and normalization."""

from __future__ import annotations

from app.models.workbook import Workbook


def test_to_dict_adds_default_sheet_and_clamps_active_index() -> None:
    workbook = Workbook(name="Model", sheets=[], active_sheet_index=99)

    payload = workbook.to_dict()

    assert payload["active_sheet_index"] == 0
    assert len(payload["sheets"]) == 1
    assert payload["sheets"][0]["name"] == "Sheet1"


def test_from_dict_defaults_invalid_active_sheet_index() -> None:
    workbook = Workbook.from_dict(
        {
            "name": "Imported",
            "active_sheet_index": "not-an-int",
            "sheets": [{"name": "SheetA", "cells": {}}],
        }
    )

    assert workbook.active_sheet_index == 0
    assert workbook.get_active_sheet().name == "SheetA"


def test_to_dict_includes_schema_version() -> None:
    workbook = Workbook(name="Schema")
    payload = workbook.to_dict()

    assert payload["metadata"]["schema_version"] == "1.2"
