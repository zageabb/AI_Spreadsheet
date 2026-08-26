"""Migrate local JSON workbooks into PostgreSQL."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from app.storage.json_storage import JsonWorkbookStorage
from app.storage.postgres_storage import PostgresWorkbookStorage


def migrate_directory(
    json_dir: Path,
    *,
    key_prefix: str = "",
    dry_run: bool = False,
    continue_on_error: bool = False,
) -> tuple[int, list[tuple[Path, str]]]:
    """Migrate every JSON workbook and return successes plus failures."""
    json_storage = JsonWorkbookStorage()
    postgres_storage = PostgresWorkbookStorage()

    migrated = 0
    failures: list[tuple[Path, str]] = []
    for source in sorted(json_dir.glob("*.json")):
        external_key = f"{key_prefix}{source.stem}"
        try:
            workbook = json_storage.load_workbook(str(source))
            if not dry_run:
                postgres_storage.save_workbook(external_key, workbook)
            migrated += 1
            verb = "Validated" if dry_run else "Migrated"
            print(f"{verb} {source.name} -> external_key '{external_key}'")
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"Failed {source.name}: {exc}")
            if not continue_on_error:
                raise

    return migrated, failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate AI Spreadsheet JSON files to PostgreSQL.")
    parser.add_argument("--source-dir", type=Path, default=Path("data"))
    parser.add_argument("--key-prefix", default="", help="Prefix applied to PostgreSQL external keys.")
    parser.add_argument("--dry-run", action="store_true", help="Validate files without writing to PostgreSQL.")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser


def main() -> int:
    load_dotenv()
    args = _parser().parse_args()
    if not args.source_dir.is_dir():
        print(f"Source directory does not exist: {args.source_dir}")
        return 2
    total, failures = migrate_directory(
        args.source_dir,
        key_prefix=args.key_prefix,
        dry_run=args.dry_run,
        continue_on_error=args.continue_on_error,
    )
    print(f"Migration completed. {total} succeeded; {len(failures)} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
