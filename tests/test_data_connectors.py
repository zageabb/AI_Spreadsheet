import csv
import sqlite3

import pytest

import app.services.data_connectors as connectors_module
from app.services.data_connectors import (DataConnectorError, DataConnectorService,
    DataSourceSpec, EnvironmentCredentialResolver)


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


def test_data_source_definitions_reject_embedded_secrets():
    with pytest.raises(DataConnectorError):
        DataSourceSpec("rest","https://example.com",{"headers":{"Authorization":"Bearer secret"}}).to_dict()
    with pytest.raises(DataConnectorError):
        DataSourceSpec("postgres_analytics","reporting",{"query":"SELECT 1","password":"secret"}).to_dict()
    with pytest.raises(DataConnectorError):
        DataSourceSpec("rest","https://example.com",{"headers":{"X-API-Key":"secret"}}).to_dict()
    with pytest.raises(DataConnectorError):
        DataSourceSpec("postgres_analytics","host=db password=secret",{"query":"SELECT 1"}).to_dict()


def test_environment_credential_resolver_supports_json_and_named_references(monkeypatch):
    monkeypatch.setenv("DATA_CREDENTIAL_FINANCE_API",'{"type":"bearer","token":"abc"}')
    assert EnvironmentCredentialResolver().resolve("finance-api")["token"]=="abc"
    with pytest.raises(DataConnectorError):EnvironmentCredentialResolver().resolve("missing")


def test_authenticated_rest_connector_uses_secret_reference_and_json_path(monkeypatch):
    captured={}
    class Response:
        headers={"Content-Type":"application/json; charset=utf-8"}
        def __enter__(self):return self
        def __exit__(self,*_):return False
        def read(self,_limit):return b'{"data":{"records":[{"name":"A","value":10},{"name":"B","value":20}]}}'
    def fake_urlopen(request,timeout):
        captured["url"]=request.full_url; captured["auth"]=request.get_header("Authorization"); captured["timeout"]=timeout; return Response()
    monkeypatch.setattr(connectors_module,"urlopen",fake_urlopen)
    monkeypatch.setenv("DATA_CREDENTIAL_REPORTS",'{"type":"bearer","token":"top-secret"}')
    source=DataSourceSpec("rest","https://example.com/report",{"credential_ref":"reports","params":{"region":"UK"},"json_path":"data.records","limit":1})
    rows=DataConnectorService().load(source)
    assert rows==[{"name":"A","value":10}]
    assert "region=UK" in captured["url"] and captured["auth"]=="Bearer top-secret"
    assert "top-secret" not in str(source.to_dict())


def test_postgres_analytics_enforces_read_only_and_limit(monkeypatch):
    calls=[]
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*_):return False
        def execute(self,query,params=None):calls.append((query,params))
        def fetchall(self):return [{"supplier":"A","value":10}]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*_):return False
        def execute(self,query,params=None):calls.append((query,params))
        def cursor(self):return Cursor()
    monkeypatch.setenv("DATA_CREDENTIAL_ANALYTICS",'{"host":"db","dbname":"reporting","user":"reader","password":"secret"}')
    monkeypatch.setattr("psycopg.connect",lambda **_kwargs:Connection())
    rows=DataConnectorService().load(DataSourceSpec("postgres_analytics","Reporting DB",{"credential_ref":"analytics","query":"SELECT supplier, value FROM spend","limit":25}))
    assert rows==[{"supplier":"A","value":10}]
    assert calls[0][0]=="SET TRANSACTION READ ONLY"
    assert calls[-1][1]==(25,)
    with pytest.raises(DataConnectorError):DataConnectorService().load_postgres(credential_ref="analytics",query="COPY spend TO STDOUT")
