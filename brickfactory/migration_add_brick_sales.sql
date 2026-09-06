-- ===========================================================================
-- MIGRATION: Brick Sales feature
-- SAFE TO RUN on your existing database — this does NOT drop or touch any
-- existing table. It only adds two new tables and one new setting.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Outlet Brick Stock — a single running total of finished bricks available
-- to sell. Separate from materials_inventory (which tracks raw materials
-- like Flyash/Sand, not finished bricks).
-- One row only (id is always 1) — a running counter, not a history log.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outlet_stock (
    id           INT PRIMARY KEY DEFAULT 1,
    total_bricks INT NOT NULL DEFAULT 0,
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO outlet_stock (id, total_bricks)
VALUES (1, 0)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Brick Sales — one row per customer sale. is_edited tracks whether a
-- same-day correction was made, same pattern as production_log's
-- is_corrected column.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brick_sales (
    sale_id           SERIAL PRIMARY KEY,
    sale_date         DATE NOT NULL,
    sale_timestamp    TIME NOT NULL,
    customer_name     VARCHAR(100) NOT NULL,
    customer_mobile   VARCHAR(15) NOT NULL,
    bricks_purchased  INT NOT NULL,
    cost_per_brick    NUMERIC(12,2) NOT NULL,
    amount_due        NUMERIC(12,2) NOT NULL,   -- bricks_purchased * cost_per_brick
    other_charges     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_amount      NUMERIC(12,2) NOT NULL,   -- amount_due + other_charges
    amount_paid       NUMERIC(12,2) NOT NULL,
    is_edited         VARCHAR(5) NOT NULL DEFAULT 'no'
);

-- ---------------------------------------------------------------------------
-- Admin-configurable default price per brick (like bricks_per_mix — lives
-- in the existing settings table, no new table needed for this part).
-- ---------------------------------------------------------------------------
INSERT INTO settings (setting_key, setting_value)
VALUES ('default_cost_per_brick', 7.50)
ON CONFLICT (setting_key) DO NOTHING;
