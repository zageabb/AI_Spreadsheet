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
- [x] Add lazy error-handling functions, dynamic arrays and structured table references
- [x] Add a Context Studio-styled transformation step builder with a 200-row preview
- [x] Persist applied transformation steps in worksheet metadata
- [x] Add refreshable CSV and read-only SQLite connectors
- [x] Reload connected sources and replay saved transformation pipelines
- [ ] Add authenticated REST API and PostgreSQL analytical connectors
- [x] Preserve validation rules and tables in XLSX round trips
- [x] Preserve supported charts, drawings, images and package relationships through an OOXML template layer

## Milestone 9 — Excel compatibility and advanced formulas
- [x] Lazy `IF`, `IFERROR`, and `IFNA` evaluation
- [x] Spill-capable `SEQUENCE`, `FILTER`, `SORT`, and `UNIQUE`
- [x] `#SPILL!` collision handling and downstream recalculation
- [x] Excel table-column references such as `SalesTable[Amount]`
- [x] XLSX table and data-validation round trips
- [x] Regression tests and compatibility documentation

## Post-Phase 9 — Extensibility and OOXML preservation
- [x] Verified, size-limited OOXML package snapshots
- [x] Template-based Excel export preserving charts and drawings
- [x] Context Studio-styled custom Python function editor
- [x] Validated local function persistence and immediate registration
- [x] Startup discovery for user-authored function modules
- [x] Security, round-trip and regression tests

## Phase 10 — Desktop release candidate
- [x] Timed local autosave snapshots without overwriting primary storage
- [x] Identity-scoped startup recovery and snapshot cleanup
- [x] Unsaved-change close confirmation
- [x] Recent local workbook menu
- [x] Recovery status in the Context Studio status bar
- [x] PyInstaller configuration and reproducible checksum build script
- [x] Windows, macOS and Ubuntu GitHub Actions build matrix
- [x] Release documentation and regression tests

## Phase 11 — Grounded AI spreadsheet copilot
- [x] Context Studio right-side assistant dock
- [x] Bounded selected-cell context with large-selection protection
- [x] Configurable Ollama and OpenAI-compatible providers
- [x] Formula explanation, selection analysis and proposed cell changes
- [x] Strict response and proposal validation
- [x] Explicit approval before edits; no silent workbook mutation
- [x] Read-only permission enforcement and graceful offline behaviour
- [x] Security, grounding and regression tests

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
- [x] FastAPI server
- [x] WebSocket support
- [x] Presence tracking
- [x] Workbook session tracking
- [x] Current sheet visibility
- [x] Current cell/range visibility
- [x] Basic conflict-handling scaffold

## Milestone 8 — Email notifications and hardening
- [x] Invite/access emails
- [x] Access removed emails
- [x] Expiring, single-use password reset flow
- [x] Tests
- [x] Validation
- [x] README cleanup
- [x] Packaging notes
