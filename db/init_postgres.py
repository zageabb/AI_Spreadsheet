"""Initialize PostgreSQL schema for AI Spreadsheet."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from app.storage.postgres_db import PostgresDatabase


def main() -> int:
    load_dotenv()
    schema_path = Path(__file__).with_name("schema.sql")
    PostgresDatabase().run_schema_file(schema_path)
    print(f"Applied schema from {schema_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
