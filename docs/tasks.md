# AI_Spreadsheet Task Plan

## Spreadsheet core v2 — Phases 1–4
- [x] Virtualised `QTableView`/`QAbstractTableModel` sparse grid (100,000 rows, 1,024 columns by default)
- [x] Excel-style coordinates, including AA+ columns, absolute references and quoted sheet names
- [x] Typed user values and separate formula/calculated-value storage
- [x] Dependency graph, affected-cell discovery, calculation ordering and circular-reference detection
- [x] Context Studio visual system translated into a reusable Qt theme
- [x] Render imported core cell formatting in the desktop grid
- [x] Preserve frozen panes, merged ranges, filters, column widths and row heights in XLSX round trips
- [x] Recorded deterministic transformation pipeline: select, rename, filter, sort and fill-null
- [x] Formula ranges, `$` references, quoted cross-sheet references and workbook-wide recalculation
- [x] Recalculate downstream cells in dependency order and report circular references as `#CIRC!`
- [x] Expand compatibility with lookup, conditional aggregate, date, text and math functions
- [ ] Add lazy error-handling functions, dynamic arrays and structured table references
- [x] Add a Context Studio-styled transformation step builder with a 200-row preview
- [x] Persist applied transformation steps in worksheet metadata
- [x] Add refreshable CSV and read-only SQLite connectors
- [x] Reload connected sources and replay saved transformation pipelines
- [ ] Add authenticated REST API and PostgreSQL analytical connectors
- [ ] Preserve charts, validation rules, tables and unsupported XLSX objects

## Milestone 1 — MVP desktop spreadsheet
- [ ] Bootstrap repository structure
- [ ] Add `requirements.txt`, `.gitignore`, `.env.example`, `README.md`
- [ ] Build PySide6 desktop shell
- [ ] Add menu bar, toolbar/ribbon, formula bar, worksheet grid, tabs, status bar
- [ ] Create workbook/sheet/cell models
- [ ] Implement JSON storage adapter
- [ ] Load/save sample workbook
- [ ] Bind worksheet grid to workbook data
- [ ] Add basic formatting support

## Milestone 2 — Formula engine and plugins
- [ ] Build formula parser/evaluator foundation
- [ ] Support cell references like `A1`
- [ ] Implement starter function set:
  - [ ] SUM
  - [ ] AVERAGE
  - [ ] MIN
  - [ ] MAX
  - [ ] COUNT
  - [ ] IF
  - [ ] AND
  - [ ] OR
  - [ ] NOT
  - [ ] ROUND
  - [ ] ABS
  - [ ] CONCAT
  - [ ] LEFT
  - [ ] RIGHT
  - [ ] LEN
- [ ] Load built-in formulas dynamically
- [ ] Add custom plugin discovery from `plugins/`

## Milestone 3 — Workbook actions and formatting
- [ ] New workbook
- [ ] Open workbook
- [ ] Save
- [ ] Save as
- [ ] Add sheet
- [ ] Rename sheet
- [ ] Delete sheet
- [ ] Duplicate sheet
- [ ] Borders
- [ ] Conditional formatting first version

## Milestone 4 — Excel and CSV compatibility
- [ ] Import `.xlsx`
- [ ] Export `.xlsx`
- [ ] Import `.csv`
- [ ] Export `.csv`
- [ ] Preserve formulas where practical
- [ ] Preserve basic formatting where practical

## Milestone 5 — Authentication and permissions
- [x] Email login
- [x] Password hashing
- [x] Registration scaffold
- [x] Session/token handling
- [x] Owner/editor/viewer roles
- [x] Grant/revoke access workflows

## Milestone 6 — PostgreSQL backend
- [x] Schema SQL
- [x] Python DB layer
- [x] Storage adapter
- [x] Config examples
- [x] JSON-to-PostgreSQL migration notes/script

## Milestone 7 — Collaboration server
- [ ] FastAPI server
- [ ] WebSocket support
- [ ] Presence tracking
- [ ] Workbook session tracking
- [ ] Current sheet visibility
- [ ] Current cell/range visibility
- [ ] Basic conflict-handling scaffold

## Milestone 8 — Email notifications and hardening
- [ ] Invite/access emails
- [ ] Access removed emails
- [ ] Password reset scaffold
- [ ] Tests
- [ ] Validation
- [ ] README cleanup
- [ ] Packaging notes
