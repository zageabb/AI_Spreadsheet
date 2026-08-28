# Phase 14 data connections

Phase 14 adds workbook-safe analytical sources through **Data → Data Connections** (`Ctrl+Shift+D`). CSV and SQLite connections remain available alongside authenticated REST and read-only PostgreSQL.

## Credential references

Connection profiles never contain passwords, tokens, API keys, DSNs or authorization headers. They contain a short reference such as `reports` or `reporting_db`. At runtime the desktop resolves that reference from an environment variable whose name starts with `DATA_CREDENTIAL_`.

Examples for a local `.env` or deployment environment (never commit real values):

```dotenv
DATA_CREDENTIAL_REPORTS={"type":"bearer","token":"real-token"}
DATA_CREDENTIAL_BASIC_API={"type":"basic","username":"reader","password":"real-password"}
DATA_CREDENTIAL_CUSTOM_HEADER={"type":"header","name":"X-API-Key","value":"real-key"}
DATA_CREDENTIAL_REPORTING_DB={"host":"db.example.com","dbname":"reporting","user":"reader","password":"real-password","sslmode":"require"}
```

Reference `reporting-db` maps to `DATA_CREDENTIAL_REPORTING_DB`. A plain-text REST credential is treated as a bearer token; PostgreSQL plain text is treated as a psycopg connection string.

## REST safety boundary

- GET requests only
- HTTPS required for remote hosts; localhost HTTP is allowed for development
- Embedded URL credentials and secret headers are rejected
- Configurable parameters, non-secret headers and dot-separated JSON paths
- Response size, timeout and row limits
- JSON must resolve to an object or array of objects
- HTTPS-to-HTTP redirect downgrade is rejected

Set `DATA_ALLOW_INSECURE_HTTP=true` only for a controlled private development endpoint.

## PostgreSQL safety boundary

- `SELECT` or `WITH` statements only
- Write, DDL, administration, `COPY`, procedure and multi-statement operations rejected
- Database transaction explicitly set read-only
- Server-side statement timeout
- Outer row limit of at most 1,000,000 rows
- Credentials resolved only at execution time

Use a PostgreSQL account that already has read-only database permissions. Application checks are defence in depth, not a replacement for database grants.

## Preview, load and refresh

The connection manager previews at most 50 rows before loading. Loading writes source data into the active worksheet, saves the secret-free source definition, and resets its transformation list. **Refresh Data** reconnects, reloads the source and replays the saved deterministic transformation pipeline. The status bar reports loading, failure and refreshed row counts.
