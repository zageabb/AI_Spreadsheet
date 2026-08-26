from __future__ import annotations

from app.models.workbook import Workbook
from app.storage.json_storage import JsonWorkbookStorage
from db.json_to_postgres import migrate_directory


def test_migration_dry_run_validates_without_database(tmp_path):
    workbook = Workbook(name="Budget")
    workbook.add_sheet("Inputs").get_cell("A1").value = 42
    JsonWorkbookStorage().save_workbook(str(tmp_path / "budget.json"), workbook)

    migrated, failures = migrate_directory(tmp_path, key_prefix="archive/", dry_run=True)

    assert migrated == 1
    assert failures == []
