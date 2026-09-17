CREATE TABLE IF NOT EXISTS customer_accounts (
 customer_id BIGSERIAL PRIMARY KEY,
 name TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
 phone_key TEXT UNIQUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK(length(trim(name))>0 OR length(trim(phone))>0)
);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS customer_id BIGINT REFERENCES customer_accounts(customer_id);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS amount_received NUMERIC(12,2);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS request_id UUID UNIQUE;
CREATE TABLE IF NOT EXISTS customer_ledger (
 entry_id BIGSERIAL PRIMARY KEY,
 customer_id BIGINT NOT NULL REFERENCES customer_accounts(customer_id),
 kind TEXT NOT NULL CHECK(kind IN ('sale','sale_payment','import_payment','payment','opening','refund','reversal')),
 amount NUMERIC(14,2) NOT NULL,
 sale_id INTEGER REFERENCES brick_sales(sale_id),
 reverses_id BIGINT UNIQUE REFERENCES customer_ledger(entry_id),
 effective_date DATE NOT NULL,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 recorded_by TEXT NOT NULL,
 note TEXT NOT NULL DEFAULT '',
 request_id UUID UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS customer_sale_debit ON customer_ledger(sale_id) WHERE kind='sale';
CREATE UNIQUE INDEX IF NOT EXISTS customer_sale_receipt ON customer_ledger(sale_id) WHERE kind IN ('sale_payment','import_payment');
CREATE INDEX IF NOT EXISTS customer_ledger_account ON customer_ledger(customer_id,entry_id);
CREATE TABLE IF NOT EXISTS customer_allocation (
 customer_id BIGINT NOT NULL REFERENCES customer_accounts(customer_id),
 sale_id INTEGER PRIMARY KEY REFERENCES brick_sales(sale_id),
 allocated NUMERIC(12,2) NOT NULL CHECK(allocated>=0)
);

ALTER TABLE brick_sales ALTER COLUMN customer_mobile TYPE VARCHAR(30);

ALTER TABLE customer_ledger ADD COLUMN IF NOT EXISTS request_data JSONB;
