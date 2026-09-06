-- ===========================================================================
-- MIGRATION: Manual Outlet Stock Adjustments
-- SAFE TO RUN on your existing database — does not touch any existing table.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS outlet_stock_adjustments (
    id                    SERIAL PRIMARY KEY,
    adjustment_date       DATE NOT NULL,
    adjustment_timestamp  TIME NOT NULL,
    change_amount         INT NOT NULL,   -- positive = stock added, negative = stock removed
    note                  TEXT,
    resulting_stock       INT NOT NULL    -- outlet total AFTER this adjustment, for easy auditing
);
