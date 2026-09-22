-- Existing invoices remain untouched. Explicit base values belong to revised/new invoices only.
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS pricing_mode TEXT NOT NULL DEFAULT 'legacy_inclusive'
    CHECK (pricing_mode IN ('legacy_inclusive', 'brick_base', 'delivered_base'));
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS entered_unit_price NUMERIC(16,6);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS brick_base_amount NUMERIC(12,2);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS transport_base_amount NUMERIC(12,2);
ALTER TABLE brick_sales ADD COLUMN IF NOT EXISTS other_base_amount NUMERIC(12,2);
-- Derived inclusive unit rates must not be truncated to two decimals.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
               AND table_name='brick_sales' AND column_name='cost_per_brick' AND numeric_scale <> 8) THEN
        ALTER TABLE brick_sales ALTER COLUMN cost_per_brick TYPE NUMERIC(20,8);
    END IF;
END $$;
