# AI_Spreadsheet Task Plan

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
