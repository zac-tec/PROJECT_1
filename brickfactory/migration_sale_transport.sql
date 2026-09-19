-- Existing invoices keep unknown transport details and unchanged totals.
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS transport_mode TEXT CHECK(transport_mode IN ('none','per_brick','flat'));
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS transport_rate NUMERIC(12,2) CHECK(transport_rate>=0);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS transport_amount NUMERIC(12,2) CHECK(transport_amount>=0);
ALTER TABLE brick_sales ALTER COLUMN transport_mode SET DEFAULT 'none';
ALTER TABLE brick_sales ALTER COLUMN transport_rate SET DEFAULT 0;
ALTER TABLE brick_sales ALTER COLUMN transport_amount SET DEFAULT 0;
