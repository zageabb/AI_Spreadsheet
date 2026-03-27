# PostgreSQL Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now implement the PostgreSQL support in a stronger and more usable way.

Goals:
- make PostgreSQL a realistic backend option
- keep JSON and PostgreSQL behind a shared storage abstraction

Tasks:
1. Refine the PostgreSQL schema
2. Add tables for:
   - users
   - workbooks
   - sheets
   - cells or equivalent workbook content structure
   - workbook permissions
   - workbook sessions/presence
3. Improve the Python database access layer
4. Add configuration examples
5. Add database initialization/setup scripts
6. Add a migration path or migration notes from JSON to PostgreSQL
7. Ensure authorization rules can work with PostgreSQL-backed workbooks

Requirements:
- use a sensible free Python PostgreSQL library
- do not hardcode credentials
- use env/config-based configuration
- keep DB logic separate from UI and business logic
- update README setup steps clearly

Output:
- updated or new database-related files
- schema SQL
- config examples
- updated README sections related to PostgreSQL
- short explanation of how the storage backend can be switched
```
