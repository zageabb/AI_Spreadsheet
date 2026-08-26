"""Initialize PostgreSQL schema for AI Spreadsheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from app.storage.postgres_db import PostgresDatabase


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Initialize the AI Spreadsheet PostgreSQL schema.")
    parser.add_argument("--check", action="store_true", help="Only verify database connectivity.")
    args = parser.parse_args()
    database = PostgresDatabase()
    if args.check:
        database.check_connection()
        print("PostgreSQL connection is ready.")
        return 0
    schema_path = Path(__file__).with_name("schema.sql")
    database.run_schema_file(schema_path)
    print(f"Applied schema from {schema_path}")
    migrations_dir = Path(__file__).with_name("migrations")
    for migration_path in sorted(migrations_dir.glob("*.sql")):
        database.run_schema_file(migration_path)
        print(f"Applied migration {migration_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
