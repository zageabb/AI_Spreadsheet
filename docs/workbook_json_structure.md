# Workbook JSON Structure

This project stores workbook data in JSON with a stable object layout designed to stay storage-backend agnostic.

Schema version: `1.1`.

## Top-level fields

- `name` (string): workbook display name.
- `active_sheet_index` (integer): zero-based active sheet index.
- `metadata` (object): workbook metadata (schema version, timestamps, owner, tags, description).
- `permissions` (object): sharing metadata used by permissions/auth milestones.
- `sheets` (array): list of worksheet objects.

## Worksheet object

- `name` (string): sheet tab name.
- `metadata` (object): optional sheet-level metadata like tab color/frozen rows.
- `cells` (object): map keyed by Excel-style cell address (`A1`, `B2`, etc.).

## Cell object

- `value` (string/number/bool/null): last computed or literal value.
- `formula` (string/null): formula expression, must begin with `=` when present.
- `formatting` (object): style metadata (number format, bold, colors, and future extensions).

## Permissions object

- `owner` (string/null): workbook owner identity.
- `shared_with` (array): objects containing:
  - `user` (string, required)
  - `role` (string, optional, e.g. `viewer`, `editor`)

## Validation and reliability behavior

`JsonWorkbookStorage` validates essential schema requirements on both load and save:

- workbook payload must be a JSON object with non-empty `name`
- `sheets` must be a non-empty list
- `active_sheet_index` must be integer and within range
- `metadata` and `permissions` must be objects when present
- `permissions.shared_with` must be a list of `{user, role?}` objects
- every sheet must have a non-empty `name`, object `metadata`, and object `cells`
- every cell key must be an Excel-style address (`A1`, `AA22`)
- `formula` must be null/string and start with `=` when provided
- `formatting` must be an object when present

Load/save behavior is hardened for reliability:

- load failures raise `StorageValidationError` with clearer messages for missing files and malformed JSON
- saves use a temporary file followed by an atomic replace to reduce corruption risk
- workbook permissions are normalized with default fields (`owner`, `shared_with`)

This keeps persistence predictable while preserving the storage abstraction used by the rest of the app.
