"""Refreshable, read-only data connectors for analytical worksheets."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen


class DataConnectorError(ValueError):
    """Raised when a source cannot be read safely."""


@dataclass(slots=True)
class DataSourceSpec:
    kind: str
    location: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        _validate_secret_free(self.options)
        _validate_location(self.location)
        return {"kind": self.kind, "location": self.location, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DataSourceSpec":
        source=cls(str(payload["kind"]), str(payload["location"]), dict(payload.get("options", {})))
        source.to_dict(); return source


class DataConnectorService:
    """Dispatch data-source specifications without coupling them to the UI."""

    def __init__(self, credentials: "EnvironmentCredentialResolver | None" = None) -> None:
        self.credentials = credentials or EnvironmentCredentialResolver()

    def load(self, source: DataSourceSpec) -> list[dict[str, Any]]:
        if source.kind == "csv":
            return self.load_csv(source.location, **source.options)
        if source.kind == "sqlite":
            return self.load_sqlite(source.location, **source.options)
        if source.kind == "rest":
            return self.load_rest(source.location, **source.options)
        if source.kind == "postgres_analytics":
            return self.load_postgres(**source.options)
        raise DataConnectorError(f"Unsupported data source: {source.kind}")

    def preview(self, source: DataSourceSpec, limit: int = 50) -> list[dict[str, Any]]:
        options=dict(source.options); options["limit"]=max(1,min(int(limit),200))
        return self.load(DataSourceSpec(source.kind,source.location,options))

    def load_rest(self, url: str, *, credential_ref: str = "", params: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None, json_path: str = "", limit: int = 100_000,
                  timeout: int = 30, max_bytes: int = 10_000_000) -> list[dict[str, Any]]:
        parsed=urlparse(url)
        if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
            raise DataConnectorError("REST source must be a valid HTTP(S) URL without embedded credentials")
        if parsed.scheme=="http" and parsed.hostname not in {"localhost","127.0.0.1","::1"} and os.getenv("DATA_ALLOW_INSECURE_HTTP","false").lower()!="true":
            raise DataConnectorError("Remote REST sources require HTTPS")
        safe_limit=max(1,min(int(limit),1_000_000)); safe_timeout=max(1,min(int(timeout),120)); safe_bytes=max(1_024,min(int(max_bytes),50_000_000))
        request_headers={str(key):str(value) for key,value in (headers or {}).items()}
        for name in request_headers:
            if name.casefold() in {"authorization","proxy-authorization","cookie","set-cookie","x-api-key"}:
                raise DataConnectorError(f"Secret header '{name}' must come from a credential reference")
        if credential_ref:
            _apply_rest_credential(request_headers,self.credentials.resolve(credential_ref))
        query=dict(parse_qsl(parsed.query,keep_blank_values=True)); query.update({str(k):str(v) for k,v in (params or {}).items()})
        target=urlunparse(parsed._replace(query=urlencode(query)))
        try:
            with urlopen(Request(target,headers=request_headers,method="GET"),timeout=safe_timeout) as response:
                final_url=getattr(response,"geturl",lambda:target)()
                if urlparse(final_url).scheme=="http" and parsed.scheme=="https":raise DataConnectorError("REST redirect attempted to downgrade HTTPS")
                content_type=response.headers.get("Content-Type","")
                if "json" not in content_type.lower():raise DataConnectorError("REST source did not return JSON")
                payload=response.read(safe_bytes+1)
                if len(payload)>safe_bytes:raise DataConnectorError("REST response exceeded the configured size limit")
        except HTTPError as exc:raise DataConnectorError(f"REST request failed with HTTP {exc.code}") from exc
        except (URLError,OSError,TimeoutError) as exc:raise DataConnectorError(f"REST request failed: {exc}") from exc
        try:data=json.loads(payload.decode("utf-8"))
        except (UnicodeError,json.JSONDecodeError) as exc:raise DataConnectorError("REST response was not valid UTF-8 JSON") from exc
        for segment in [item for item in json_path.split(".") if item]:
            if not isinstance(data,dict) or segment not in data:raise DataConnectorError(f"JSON path not found: {json_path}")
            data=data[segment]
        if isinstance(data,dict):data=[data]
        if not isinstance(data,list) or any(not isinstance(row,dict) for row in data):
            raise DataConnectorError("REST JSON path must resolve to an object or array of objects")
        return [{str(key):value for key,value in row.items()} for row in data[:safe_limit]]

    def load_postgres(self, *, credential_ref: str, query: str, limit: int = 100_000,
                      statement_timeout_ms: int = 30_000) -> list[dict[str, Any]]:
        statement=_safe_select(query); safe_limit=max(1,min(int(limit),1_000_000)); timeout=max(1_000,min(int(statement_timeout_ms),300_000))
        credential=self.credentials.resolve(credential_ref)
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:raise DataConnectorError("psycopg is required for PostgreSQL analytics") from exc
        kwargs=credential if isinstance(credential,dict) else {"conninfo":str(credential)}
        try:
            with connect(**kwargs,row_factory=dict_row) as connection:
                connection.execute("SET TRANSACTION READ ONLY")
                connection.execute("SET LOCAL statement_timeout = %s",(timeout,))
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM ({statement}) AS source_data LIMIT %s",(safe_limit,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            raise DataConnectorError(f"PostgreSQL analytical query failed: {exc}") from exc

    @staticmethod
    def load_csv(path: str, encoding: str = "utf-8-sig", delimiter: str = ",") -> list[dict[str, Any]]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():raise DataConnectorError(f"CSV file not found: {source}")
        try:
            with source.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle, delimiter=delimiter)
                if not reader.fieldnames:return []
                return [{str(key): _scalar(value) for key, value in row.items()} for row in reader]
        except (OSError, UnicodeError, csv.Error) as exc:raise DataConnectorError(f"Could not read CSV source: {exc}") from exc

    @staticmethod
    def list_sqlite_tables(path: str) -> list[str]:
        with _readonly_sqlite(path) as connection:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def load_sqlite(path: str, table: str | None = None, query: str | None = None,
                    limit: int = 100_000) -> list[dict[str, Any]]:
        if query:statement = _safe_select(query)
        elif table:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):raise DataConnectorError("Invalid SQLite table name")
            statement = f'SELECT * FROM "{table}"'
        else:raise DataConnectorError("SQLite source requires a table or SELECT query")
        safe_limit = max(1, min(int(limit), 1_000_000))
        with _readonly_sqlite(path) as connection:
            connection.row_factory = sqlite3.Row
            try:
                cursor = connection.execute(f"SELECT * FROM ({statement}) AS source_data LIMIT ?", (safe_limit,))
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as exc:raise DataConnectorError(f"SQLite query failed: {exc}") from exc


class EnvironmentCredentialResolver:
    """Resolve named secrets from process environment without persisting them in workbooks."""

    prefix="DATA_CREDENTIAL_"

    def resolve(self, reference: str) -> str | dict[str,Any]:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}",reference or ""):
            raise DataConnectorError("Credential reference must use letters, numbers, hyphens or underscores")
        env_name=self.prefix+re.sub(r"[^A-Za-z0-9]","_",reference).upper()
        raw=os.getenv(env_name,"")
        if not raw:raise DataConnectorError(f"Credential reference '{reference}' is not configured")
        try:value=json.loads(raw)
        except json.JSONDecodeError:return raw
        if not isinstance(value,dict):raise DataConnectorError(f"Credential '{reference}' must be text or a JSON object")
        return value

def _readonly_sqlite(path: str):
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise DataConnectorError(f"SQLite database not found: {source}")
    return sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)


def _safe_select(query: str) -> str:
    statement = query.strip().rstrip(";").strip()
    if ";" in statement or not re.match(r"^(SELECT|WITH)\b", statement, re.IGNORECASE):
        raise DataConnectorError("Only one read-only SELECT statement is allowed")
    blocked = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|COPY|CALL|DO|GRANT|REVOKE|TRUNCATE|MERGE|LOCK|SET|RESET)\b", re.IGNORECASE)
    if blocked.search(statement):
        raise DataConnectorError("The query contains a write or administrative operation")
    return statement


def _validate_secret_free(options: dict[str,Any]) -> None:
    blocked={"password","token","secret","api_key","apikey","authorization","proxy-authorization","cookie","set-cookie","x-api-key","dsn","conninfo"}
    def visit(value,path="options"):
        if isinstance(value,dict):
            for key,item in value.items():
                if str(key).casefold() in blocked:raise DataConnectorError(f"Secrets cannot be stored in data source definitions ({path}.{key})")
                visit(item,f"{path}.{key}")
        elif isinstance(value,(list,tuple)):
            for index,item in enumerate(value):visit(item,f"{path}[{index}]")
    visit(options)


def _validate_location(location: str) -> None:
    text=str(location)
    if re.search(r"(?i)(password|pwd|token|api[_-]?key)\s*=",text):
        raise DataConnectorError("Connection locations cannot contain credentials")
    parsed=urlparse(text)
    if parsed.username or parsed.password:
        raise DataConnectorError("Connection locations cannot contain embedded credentials")


def _apply_rest_credential(headers: dict[str,str],credential: str | dict[str,Any]) -> None:
    if isinstance(credential,str):headers["Authorization"]="Bearer "+credential; return
    kind=str(credential.get("type") or "bearer").lower()
    if kind=="bearer":headers["Authorization"]="Bearer "+str(credential.get("token") or "")
    elif kind=="basic":
        encoded=base64.b64encode(f"{credential.get('username','')}:{credential.get('password','')}".encode()).decode()
        headers["Authorization"]="Basic "+encoded
    elif kind=="header":
        name=str(credential.get("name") or "X-API-Key")
        if "\r" in name or "\n" in name:raise DataConnectorError("Invalid credential header name")
        headers[name]=str(credential.get("value") or "")
    else:raise DataConnectorError(f"Unsupported REST credential type: {kind}")


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
