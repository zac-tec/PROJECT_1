CREATE TABLE IF NOT EXISTS historical_ledger_imports (
 import_key TEXT PRIMARY KEY, imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 cutover_date DATE NOT NULL, confirmed_closing INTEGER NOT NULL CHECK(confirmed_closing>=0), notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historical_ledger_rows (
 import_key TEXT NOT NULL REFERENCES historical_ledger_imports(import_key),
 page INTEGER NOT NULL, row_number INTEGER NOT NULL, entry_date DATE,
 data JSONB NOT NULL, PRIMARY KEY(import_key,page,row_number)
);
