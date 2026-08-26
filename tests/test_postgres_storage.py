from __future__ import annotations

from contextlib import contextmanager

import pytest

from app.models.workbook import Workbook
from app.storage.postgres_storage import (
    PostgresStorageError,
    PostgresWorkbookStorage,
    _json_object,
)


class ScriptedCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executed = []
        self.current = None

    def execute(self, query, params=()):
        self.executed.append((query, params))
        self.current = next(self.rows)

    def fetchone(self):
        return self.current

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_json_object_supports_driver_strings_and_rejects_invalid_values():
    assert _json_object('{"frozen": true}') == {"frozen": True}
    assert _json_object("not json") == {}
    assert _json_object([1, 2]) == {}


def test_authorize_new_workbook_requires_actor_to_be_owner():
    storage = PostgresWorkbookStorage()
    cursor = ScriptedCursor([None])

    with pytest.raises(PostgresStorageError, match="assign the actor as owner"):
        storage._authorize_save(
            cursor,
            "forecast",
            "editor@example.com",
            {"owner": "owner@example.com"},
        )


def test_authorize_existing_workbook_accepts_editor():
    storage = PostgresWorkbookStorage()
    cursor = ScriptedCursor([{"id": "workbook-id"}, {"role": "editor"}])

    role = storage._authorize_save(cursor, "forecast", "editor@example.com", {})

    assert role == "editor"


def test_save_rejects_empty_external_key_before_connecting():
    class NeverConnectDatabase:
        @contextmanager
        def transaction(self):
            raise AssertionError("database should not be contacted")
            yield

    workbook = Workbook(name="Forecast")
    workbook.add_sheet("Sheet1")
    storage = PostgresWorkbookStorage(database=NeverConnectDatabase())

    with pytest.raises(PostgresStorageError, match="cannot be empty"):
        storage.save_workbook("  ", workbook)


def test_editor_save_does_not_rewrite_permissions():
    cursor = ScriptedCursor(
        [
            {"id": "workbook-id"},
            {"role": "editor"},
            {"id": "workbook-id"},
            None,
            {"id": "sheet-id"},
        ]
    )

    class FakeConnection:
        def cursor(self):
            return cursor

    class FakeDatabase:
        @contextmanager
        def transaction(self):
            yield FakeConnection()

    workbook = Workbook(name="Forecast")
    workbook.add_sheet("Sheet1")
    workbook.permissions = {
        "owner": "attacker@example.com",
        "shared_with": [],
    }

    PostgresWorkbookStorage(database=FakeDatabase()).save_workbook_for_user(
        "forecast", workbook, "editor@example.com"
    )

    sql = "\n".join(query for query, _params in cursor.executed)
    assert "DELETE FROM workbook_permissions" not in sql
    assert "UPDATE workbooks SET owner_user_id" not in sql
