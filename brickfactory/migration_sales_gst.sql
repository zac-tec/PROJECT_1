ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS gst_rate NUMERIC(5,2);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS taxable_amount NUMERIC(12,2);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS gst_amount NUMERIC(12,2);
CREATE TABLE IF NOT EXISTS sale_price_revision_audit (
 id BIGSERIAL PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES brick_sales(sale_id),
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(), reason TEXT NOT NULL,
 previous_record JSONB NOT NULL
);
