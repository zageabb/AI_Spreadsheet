# Workbook JSON Structure

This project stores workbook data in JSON using a stable object layout designed to stay storage-backend agnostic.

## Top-level fields

- `name` (string): workbook display name.
- `active_sheet_index` (integer): zero-based active sheet index.
- `metadata` (object): workbook metadata (schema version, timestamps, owner, tags, description).
- `permissions` (object): sharing metadata used by permissions/auth milestones.
- `sheets` (array): list of worksheet objects.

## Worksheet object

- `name` (string): sheet tab name.
- `metadata` (object): optional sheet-level metadata like tab color.
- `cells` (object): map keyed by cell address (`A1`, `B2`, etc.).

## Cell object

- `value` (string/number/bool/null): last computed or literal value.
- `formula` (string/null): formula expression beginning with `=` when present.
- `formatting` (object): style metadata (number format, bold, colors, and future extensions).

## Validation behavior

`JsonWorkbookStorage` validates essential schema requirements on both load and save:

- workbook name must be a non-empty string
- sheets must be a non-empty list
- active sheet index must be in range
- metadata/permissions must be JSON objects when present
- every sheet must have a valid name and cells object
- every cell entry must be an object, and formatting must be an object when present

This keeps persistence predictable while preserving the storage abstraction used by the rest of the app.
