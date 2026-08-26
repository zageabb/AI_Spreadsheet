from __future__ import annotations

import pytest

from app.storage import JsonWorkbookStorage, get_workbook_storage
from app.storage.postgres_config import PostgresConfig


def test_postgres_config_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5440")
    monkeypatch.setenv("POSTGRES_DB", "sheet")
    monkeypatch.setenv("POSTGRES_USER", "sheet_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_SSLMODE", "require")

    config = PostgresConfig.from_env()

    assert config.host == "db.internal"
    assert config.port == 5440
    assert config.database == "sheet"
    assert config.user == "sheet_user"
    assert config.password == "secret"
    assert config.sslmode == "require"


def test_postgres_config_from_env_rejects_non_integer_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "invalid")
    with pytest.raises(ValueError):
        PostgresConfig.from_env()


def test_postgres_config_from_env_rejects_invalid_sslmode(monkeypatch):
    monkeypatch.setenv("POSTGRES_SSLMODE", "sometimes")
    with pytest.raises(ValueError):
        PostgresConfig.from_env()


def test_get_workbook_storage_defaults_to_json(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    storage = get_workbook_storage()
    assert isinstance(storage, JsonWorkbookStorage)


def test_get_workbook_storage_postgres_selection_imports_adapter(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    storage = get_workbook_storage()
    assert storage.__class__.__name__ == "PostgresWorkbookStorage"


def test_postgres_config_rejects_out_of_range_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "70000")
    with pytest.raises(ValueError, match="between 1 and 65535"):
        PostgresConfig.from_env()


def test_postgres_config_rejects_invalid_connect_timeout(monkeypatch):
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "0")
    with pytest.raises(ValueError, match="positive integer"):
        PostgresConfig.from_env()


def test_get_workbook_storage_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "postgress")
    with pytest.raises(ValueError, match="json.*postgres"):
        get_workbook_storage()
