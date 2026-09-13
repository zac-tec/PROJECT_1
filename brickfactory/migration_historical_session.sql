CREATE TABLE IF NOT EXISTS historical_entry_session (
 id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','applied')),
 payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_by TEXT NOT NULL, applied_at TIMESTAMPTZ
);
