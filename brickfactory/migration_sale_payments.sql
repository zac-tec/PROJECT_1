CREATE TABLE IF NOT EXISTS sale_payment_audit (
 id BIGSERIAL PRIMARY KEY,
 sale_id INTEGER NOT NULL REFERENCES brick_sales(sale_id),
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 recorded_by TEXT NOT NULL,
 previous_paid NUMERIC(12,2) NOT NULL,
 new_paid NUMERIC(12,2) NOT NULL
);
