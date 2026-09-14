CREATE TABLE IF NOT EXISTS historical_labour_entries (
 entry_date DATE PRIMARY KEY, labour_hours NUMERIC(10,2) NOT NULL CHECK(labour_hours>=0),
 hourly_rate NUMERIC(10,2) NOT NULL DEFAULT 81.25, revision INTEGER NOT NULL DEFAULT 1,
 updated_by TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS historical_labour_audit (
 id BIGSERIAL PRIMARY KEY, entry_date DATE NOT NULL, old_hours NUMERIC(10,2),
 new_hours NUMERIC(10,2) NOT NULL, changed_by TEXT NOT NULL, changed_at TIMESTAMPTZ NOT NULL DEFAULT now());
