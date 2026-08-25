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
- [ ] Extend formula parser to ranges, cross-sheet evaluation and the Excel compatibility function target
- [ ] Add transformation preview/editor UI and database/API connectors
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
- [ ] Email login
- [ ] Password hashing
- [ ] Registration scaffold
- [ ] Session/token handling
- [ ] Owner/editor/viewer roles
- [ ] Grant/revoke access workflows

## Milestone 6 — PostgreSQL backend
- [ ] Schema SQL
- [ ] Python DB layer
- [ ] Storage adapter
- [ ] Config examples
- [ ] JSON-to-PostgreSQL migration notes/script

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
