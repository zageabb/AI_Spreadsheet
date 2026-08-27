# Editing essentials

Phase 12 makes routine desktop editing reversible and keyboard friendly.

## Undo and redo

Cell edits, formula-bar edits, multi-cell paste, clearing, formatting, structural row/column changes, sorting, replacement and approved AI proposals are recorded on the workbook undo stack. Opening, importing, recovering or creating a workbook clears the stack so commands cannot affect a previously loaded workbook.

## Find and replace

Use **Edit → Find and Replace** or `Ctrl+F`. The modeless panel searches values and formulas, wraps from the last cell to the first match, supports case matching, and offers single-cell or workbook-wide replacement.

## Rows, columns, sorting and filters

The **Sheet** menu inserts or deletes the selected number of rows or columns. Local A1 formula references move with structural edits; references deleted by the operation become `#REF!`. Qualified references to another worksheet are left unchanged.

The **Data** menu sorts the selected rectangle using the active column. Row filtering hides rows in the current view and never mutates workbook data; **Clear Row Filter** restores them.

## Formatting and navigation

The toolbar and **Format** menu provide bold, italic, underline, fill colour, font colour, and common number formats. Useful keyboard commands include:

- `F2` — edit the active cell
- `Delete` — clear the selection
- `Ctrl+Home` — go to A1
- `Ctrl+End` — go to the last used cell
- `Ctrl+Z` / `Ctrl+Y` — undo / redo

Viewer permissions disable all mutating editing operations.
