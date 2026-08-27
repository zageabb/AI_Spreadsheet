"""Tests for autosave snapshots and recovery isolation."""

from __future__ import annotations

from app.models.workbook import Workbook
from app.services.recovery import RecoveryManager


def test_recovery_snapshot_roundtrip_does_not_modify_live_metadata(tmp_path):
    workbook = Workbook(name="Unsaved plan")
    workbook.add_sheet("Sheet1").get_cell("A1").value = "draft"
    manager = RecoveryManager(tmp_path)

    path = manager.snapshot(workbook, "/work/plan.json", "owner@example.com")

    assert path.exists()
    assert "_recovery" not in workbook.metadata
    candidates = manager.candidates("owner@example.com")
    assert len(candidates) == 1
    assert candidates[0].source_path == "/work/plan.json"
    restored = manager.restore(candidates[0])
    assert restored.sheets[0].get_cell("A1").value == "draft"
    assert "_recovery" not in restored.metadata


def test_recovery_candidates_are_identity_scoped_and_discardable(tmp_path):
    manager = RecoveryManager(tmp_path)
    first = Workbook(name="First"); first.add_sheet("Sheet1")
    second = Workbook(name="Second"); second.add_sheet("Sheet1")
    manager.snapshot(first, None, "first@example.com")
    second_path = manager.snapshot(second, None, "second@example.com")

    assert [item.workbook_name for item in manager.candidates("first@example.com")] == ["First"]
    manager.discard(second_path)
    assert manager.candidates("second@example.com") == []
