-- PostgreSQL schema for AI Spreadsheet.
-- This schema keeps JSON as default local storage while enabling PostgreSQL
-- as an alternative backend via app.storage.postgres_storage.PostgresWorkbookStorage.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workbooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  active_sheet_index INTEGER NOT NULL DEFAULT 0 CHECK (active_sheet_index >= 0),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sheets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workbook_id UUID NOT NULL REFERENCES workbooks(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  name TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (workbook_id, position),
  UNIQUE (workbook_id, name)
);

CREATE TABLE IF NOT EXISTS cells (
  sheet_id UUID NOT NULL REFERENCES sheets(id) ON DELETE CASCADE,
  address TEXT NOT NULL,
  value_json JSONB,
  formula TEXT,
  formatting JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (sheet_id, address),
  CONSTRAINT cells_address_check CHECK (address ~ '^[A-Z]+[1-9][0-9]*$')
);

CREATE TABLE IF NOT EXISTS workbook_permissions (
  workbook_id UUID NOT NULL REFERENCES workbooks(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (workbook_id, user_id),
  CONSTRAINT workbook_permissions_role_check CHECK (role IN ('owner', 'editor', 'viewer'))
);

CREATE TABLE IF NOT EXISTS workbook_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workbook_id UUID NOT NULL REFERENCES workbooks(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  current_sheet_name TEXT,
  current_cell_address TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workbooks_external_key ON workbooks(external_key);
CREATE INDEX IF NOT EXISTS idx_sheets_workbook_id ON sheets(workbook_id);
CREATE INDEX IF NOT EXISTS idx_cells_sheet_id ON cells(sheet_id);
CREATE INDEX IF NOT EXISTS idx_permissions_workbook_role ON workbook_permissions(workbook_id, role);
CREATE INDEX IF NOT EXISTS idx_sessions_workbook_active ON workbook_sessions(workbook_id, is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_permissions_single_owner
  ON workbook_permissions(workbook_id) WHERE role = 'owner';

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;
CREATE TRIGGER trg_users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_workbooks_set_updated_at ON workbooks;
CREATE TRIGGER trg_workbooks_set_updated_at
BEFORE UPDATE ON workbooks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_sheets_set_updated_at ON sheets;
CREATE TRIGGER trg_sheets_set_updated_at
BEFORE UPDATE ON sheets
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_permissions_set_updated_at ON workbook_permissions;
CREATE TRIGGER trg_permissions_set_updated_at
BEFORE UPDATE ON workbook_permissions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
