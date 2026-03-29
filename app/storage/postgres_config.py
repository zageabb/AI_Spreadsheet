"""PostgreSQL configuration helpers for storage adapters and setup scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass

_ALLOWED_SSLMODES = {
    "disable",
    "allow",
    "prefer",
    "require",
    "verify-ca",
    "verify-full",
}


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    """Configuration model for PostgreSQL connections.

    Values are loaded from environment variables to avoid hardcoded credentials.
    """

    host: str = "localhost"
    port: int = 5432
    database: str = "ai_spreadsheet"
    user: str = "spreadsheet_user"
    password: str = ""
    sslmode: str = "prefer"

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """Create config from env vars.

        Supported variables:
        - POSTGRES_HOST
        - POSTGRES_PORT
        - POSTGRES_DB
        - POSTGRES_USER
        - POSTGRES_PASSWORD
        - POSTGRES_SSLMODE
        """

        host = os.getenv("POSTGRES_HOST", "localhost").strip() or "localhost"
        database = os.getenv("POSTGRES_DB", "ai_spreadsheet").strip() or "ai_spreadsheet"
        user = os.getenv("POSTGRES_USER", "spreadsheet_user").strip() or "spreadsheet_user"
        password = os.getenv("POSTGRES_PASSWORD", "")

        try:
            port = int(os.getenv("POSTGRES_PORT", "5432"))
        except ValueError as exc:
            raise ValueError("POSTGRES_PORT must be an integer.") from exc
        if port <= 0:
            raise ValueError("POSTGRES_PORT must be a positive integer.")

        sslmode = os.getenv("POSTGRES_SSLMODE", "prefer").strip().lower() or "prefer"
        if sslmode not in _ALLOWED_SSLMODES:
            raise ValueError("POSTGRES_SSLMODE must be one of disable, allow, prefer, require, verify-ca, verify-full.")

        return cls(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            sslmode=sslmode,
        )

    def connection_kwargs(self) -> dict[str, str | int]:
        """Return keyword args for psycopg.connect."""
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "sslmode": self.sslmode,
        }
