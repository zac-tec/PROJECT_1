-- Preserve unknown recording dates for existing invoices.
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMPTZ;
ALTER TABLE brick_sales ALTER COLUMN recorded_at SET DEFAULT CURRENT_TIMESTAMP;
