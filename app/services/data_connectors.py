"""Refreshable, read-only data connectors for analytical worksheets."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
import re
import sqlite3
from typing import Any


class DataConnectorError(ValueError):
    """Raised when a source cannot be read safely."""


@dataclass(slots=True)
class DataSourceSpec:
    kind: str
    location: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "location": self.location, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataSourceSpec":
        return cls(str(payload["kind"]), str(payload["location"]), dict(payload.get("options", {})))


class DataConnectorService:
    """Dispatch data-source specifications without coupling them to the UI."""

    def load(self, source: DataSourceSpec) -> list[dict[str, Any]]:
        if source.kind == "csv":
            return self.load_csv(source.location, **source.options)
        if source.kind == "sqlite":
            return self.load_sqlite(source.location, **source.options)
        raise DataConnectorError(f"Unsupported data source: {source.kind}")

    @staticmethod
    def load_csv(path: str, encoding: str = "utf-8-sig", delimiter: str = ",") -> list[dict[str, Any]]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise DataConnectorError(f"CSV file not found: {source}")
        try:
            with source.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle, delimiter=delimiter)
                if not reader.fieldnames:
                    return []
                return [{str(key): _scalar(value) for key, value in row.items()} for row in reader]
        except (OSError, UnicodeError, csv.Error) as exc:
            raise DataConnectorError(f"Could not read CSV source: {exc}") from exc

    @staticmethod
    def list_sqlite_tables(path: str) -> list[str]:
        with _readonly_sqlite(path) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def load_sqlite(path: str, table: str | None = None, query: str | None = None,
                    limit: int = 100_000) -> list[dict[str, Any]]:
        if query:
            statement = _safe_select(query)
        elif table:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
                raise DataConnectorError("Invalid SQLite table name")
            statement = f'SELECT * FROM "{table}"'
        else:
            raise DataConnectorError("SQLite source requires a table or SELECT query")
        safe_limit = max(1, min(int(limit), 1_000_000))
        with _readonly_sqlite(path) as connection:
            connection.row_factory = sqlite3.Row
            try:
                cursor = connection.execute(f"SELECT * FROM ({statement}) AS source_data LIMIT ?", (safe_limit,))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as exc:
                raise DataConnectorError(f"SQLite query failed: {exc}") from exc


def _readonly_sqlite(path: str):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise DataConnectorError(f"SQLite database not found: {source}")
    return sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)


def _safe_select(query: str) -> str:
    statement = query.strip().rstrip(";").strip()
    if ";" in statement or not re.match(r"^(SELECT|WITH)\b", statement, re.IGNORECASE):
        raise DataConnectorError("Only one read-only SELECT statement is allowed")
    blocked = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM)\b", re.IGNORECASE)
    if blocked.search(statement):
        raise DataConnectorError("The query contains a write or administrative operation")
    return statement


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text.casefold() in {"true", "false"}:
        return text.casefold() == "true"
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value
