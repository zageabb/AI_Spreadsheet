# Formula Engine Prompt

```text
Read AGENTS.md and docs/tasks.md.
Execute this stage only.

Now improve the spreadsheet formula engine.

Goals:
- make the formula system more robust and easier to extend
- keep Excel 365-style naming conventions
- preserve modular runtime loading of functions

Tasks:
1. Improve formula parsing
2. Improve cell reference handling for same-sheet references like A1, B2, C10
3. Improve error handling for invalid formulas
4. Strengthen the function registry
5. Ensure built-in functions are loaded dynamically from separate modules
6. Improve support for user-defined custom functions loaded at runtime
7. Add tests or test scaffolds for formula parsing and evaluation
8. Prepare the design for future cross-sheet references, even if only scaffolded now

Keep the starter function set working:
- SUM
- AVERAGE
- MIN
- MAX
- COUNT
- IF
- AND
- OR
- NOT
- ROUND
- ABS
- CONCAT
- LEFT
- RIGHT
- LEN

Requirements:
- do not pretend to fully match Excel internals
- do provide a strong extensible foundation
- document how custom functions are added
- keep formula functions in separate files

Output:
- updated files only
- any new tests
- brief explanation of what is fully implemented vs future-ready
```
