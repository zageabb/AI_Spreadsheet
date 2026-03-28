"""PostgreSQL configuration helpers for storage adapters and setup scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass


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

        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "ai_spreadsheet"),
            user=os.getenv("POSTGRES_USER", "spreadsheet_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
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
