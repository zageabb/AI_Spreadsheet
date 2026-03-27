# Final Cleanup Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now review the full project and make it internally consistent.

Please:
1. Check the project tree against the code you produced
2. Fix missing imports
3. Fix broken references between modules
4. Ensure requirements.txt matches actual usage
5. Ensure README commands match the code structure
6. Ensure config/env examples match actual configuration keys
7. Ensure scaffolded features are clearly marked
8. Ensure the project still reflects:
   - Python desktop spreadsheet app
   - JSON-first local storage
   - PostgreSQL upgrade path
   - Excel import/export
   - plugin-based formula system
   - email login/auth foundation
   - workbook sharing roles
   - collaboration server starter

Output:
- only the corrected files
- a final note listing:
  - what is working
  - what is partial
  - what remains as scaffold
```
