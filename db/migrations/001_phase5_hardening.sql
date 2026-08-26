-- Idempotent hardening for databases created before the Phase 5 schema update.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'workbooks_active_sheet_index_check'
  ) THEN
    ALTER TABLE workbooks
      ADD CONSTRAINT workbooks_active_sheet_index_check CHECK (active_sheet_index >= 0);
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'cells_address_check'
  ) THEN
    ALTER TABLE cells
      ADD CONSTRAINT cells_address_check CHECK (address ~ '^[A-Z]+[1-9][0-9]*$');
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_single_owner
  ON workbook_permissions(workbook_id) WHERE role = 'owner';
