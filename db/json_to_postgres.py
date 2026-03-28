"""Migrate local JSON workbooks into PostgreSQL."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from app.storage.json_storage import JsonWorkbookStorage
from app.storage.postgres_storage import PostgresWorkbookStorage


def migrate_directory(json_dir: Path) -> int:
    json_storage = JsonWorkbookStorage()
    postgres_storage = PostgresWorkbookStorage()

    migrated = 0
    for source in sorted(json_dir.glob("*.json")):
        workbook = json_storage.load_workbook(str(source))
        external_key = source.stem
        postgres_storage.save_workbook(external_key, workbook)
        migrated += 1
        print(f"Migrated {source.name} -> external_key '{external_key}'")

    return migrated


def main() -> int:
    load_dotenv()
    json_dir = Path("data")
    total = migrate_directory(json_dir)
    print(f"Migration completed. {total} workbook(s) migrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
