import csv
import sqlite3

import pytest

from app.services.data_connectors import DataConnectorError, DataConnectorService, DataSourceSpec


def test_csv_source_infers_common_scalar_types(tmp_path):
    path = tmp_path / "source.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["Supplier", "Value", "Active"]); writer.writerow(["A", "12.5", "true"])
    rows = DataConnectorService().load(DataSourceSpec("csv", str(path)))
    assert rows == [{"Supplier": "A", "Value": 12.5, "Active": True}]


def test_sqlite_connector_is_read_only_and_supports_tables(tmp_path):
    path = tmp_path / "source.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE suppliers (name TEXT, value INTEGER)")
    connection.executemany("INSERT INTO suppliers VALUES (?, ?)", [("A", 10), ("B", 20)])
    connection.commit(); connection.close()
    service = DataConnectorService()
    assert service.list_sqlite_tables(str(path)) == ["suppliers"]
    assert service.load(DataSourceSpec("sqlite", str(path), {"table": "suppliers"})) == [
        {"name": "A", "value": 10}, {"name": "B", "value": 20}
    ]
    assert service.load_sqlite(str(path), query="SELECT name FROM suppliers WHERE value >= 20") == [{"name": "B"}]


def test_sqlite_connector_rejects_write_or_multiple_statements(tmp_path):
    path = tmp_path / "source.db"; sqlite3.connect(path).close()
    service = DataConnectorService()
    with pytest.raises(DataConnectorError):
        service.load_sqlite(str(path), query="DELETE FROM anything")
    with pytest.raises(DataConnectorError):
        service.load_sqlite(str(path), query="SELECT 1; DROP TABLE anything")
