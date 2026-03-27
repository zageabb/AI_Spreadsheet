# Codex Prompt Pack for AI_Spreadsheet

This folder contains the prompt sequence for building the `AI_Spreadsheet` repository in stages.

## Recommended repo placement
- `AGENTS.md` at repo root
- `docs/tasks.md`
- `docs/codex/*.md`

## Recommended execution order
1. `03_master_scaffold_prompt.md`
2. `04_ui_improvements_prompt.md`
3. `05_formula_engine_prompt.md`
4. `06_json_storage_prompt.md`
5. `07_postgresql_prompt.md`
6. `08_auth_permissions_prompt.md`
7. `09_collaboration_prompt.md`
8. `10_email_notifications_prompt.md`
9. `11_excel_import_export_prompt.md`
10. `12_tests_hardening_prompt.md`
11. `13_final_cleanup_prompt.md`

## Best practice
Before each prompt, tell Codex to read:
- `AGENTS.md`
- `docs/tasks.md`

Example:
> Read AGENTS.md and docs/tasks.md. Then execute docs/codex/03_master_scaffold_prompt.md.
