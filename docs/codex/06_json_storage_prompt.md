# JSON Storage Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now improve the workbook data model and JSON storage layer.

Goals:
- make workbook persistence reliable and easy to understand
- prepare the storage layer for later PostgreSQL use

Tasks:
1. Refine the JSON schema for workbook storage
2. Ensure workbook metadata, sheets, cells, values, formulas, formatting, and permissions metadata are represented clearly
3. Improve load/save behaviour
4. Add validation where practical
5. Keep the storage layer abstract so the rest of the app does not depend directly on JSON implementation details
6. Add sample workbook files with realistic data
7. Add comments or documentation explaining the JSON structure

Requirements:
- preserve the storage abstraction
- keep JSON as the default local backend
- make directory structure systematic and easy to follow
- do not tightly couple storage to UI code

Output:
- updated files only
- updated sample JSON files
- short explanation of the workbook JSON structure
```
