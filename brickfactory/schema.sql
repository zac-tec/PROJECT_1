-- ===========================================================================
-- BRICK FACTORY SYSTEM — FRESH SCHEMA (built from scratch)
-- Every table maps 1:1 to something the application does.
-- Fresh installs do not create users; provision them with provision_user.py.
-- ===========================================================================

DROP TABLE IF EXISTS rate_history;
DROP TABLE IF EXISTS making_charges_history;
DROP TABLE IF EXISTS recipe;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS system_users;
DROP TABLE IF EXISTS utility_bills;
DROP TABLE IF EXISTS production_log;
DROP TABLE IF EXISTS making_charges;
DROP TABLE IF EXISTS materials_inventory;

-- ---------------------------------------------------------------------------
-- 1. Materials & Stock
--    current_stock is ALWAYS a whole number — Flyash/Sand in kg, Chemical
--    in litres, Cement in packet count. Matches shared_data.py's strict-
--    integer stock rule exactly.
-- ---------------------------------------------------------------------------
CREATE TABLE materials_inventory (
    material_name  VARCHAR(50) PRIMARY KEY,
    current_stock  INT NOT NULL DEFAULT 0,
    unit_rate      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    unit_type      VARCHAR(20) NOT NULL   -- 'kg', 'L', or 'packets' — for display only
);

-- ---------------------------------------------------------------------------
-- 2. Recipe (per mix) — EDITABLE, with an icon in the web app to change it
--    later. In the terminal code this was a hardcoded RECIPE dict; here
--    it's a table so admin can update it from the UI without touching code.
-- ---------------------------------------------------------------------------
CREATE TABLE recipe (
    material_name VARCHAR(50) PRIMARY KEY REFERENCES materials_inventory(material_name),
    qty_per_mix   NUMERIC(10,3) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 3. Rate Change History — matches rate_history.txt
-- ---------------------------------------------------------------------------
CREATE TABLE rate_history (
    id                SERIAL PRIMARY KEY,
    change_date       DATE NOT NULL,
    change_timestamp  TIMESTAMP NOT NULL,
    material_name     VARCHAR(50) NOT NULL,
    old_rate          NUMERIC(12,2) NOT NULL,
    new_rate          NUMERIC(12,2) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 4. Making Charges (cost per brick — Labour, Loading, Union, Salary_Other)
-- ---------------------------------------------------------------------------
CREATE TABLE making_charges (
    charge_name    VARCHAR(50) PRIMARY KEY,
    cost_per_brick NUMERIC(12,2) NOT NULL DEFAULT 0.00
);

-- ---------------------------------------------------------------------------
-- 5. Making Charges History — matches making_charges_history.txt
-- ---------------------------------------------------------------------------
CREATE TABLE making_charges_history (
    id                SERIAL PRIMARY KEY,
    change_date       DATE NOT NULL,
    change_timestamp  TIMESTAMP NOT NULL,
    charge_name       VARCHAR(50) NOT NULL,
    old_value         NUMERIC(12,2) NOT NULL,
    new_value         NUMERIC(12,2) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 6. Daily Production Log — matches production_log.txt
--    production_date is PRIMARY KEY: exactly one row per day. A same-day
--    re-save OVERWRITES the row and sets is_corrected = 'yes' — it never
--    creates a second row for the same date. This matches
--    manager_features.py's save_entry() behavior exactly.
-- ---------------------------------------------------------------------------
CREATE TABLE production_log (
    production_date    DATE PRIMARY KEY,
    timestamp_entered  TIME NOT NULL,
    mixes_run          INT NOT NULL,
    bricks_made        INT NOT NULL,
    calculated_field   VARCHAR(20) NOT NULL DEFAULT 'none',  -- 'mixes', 'bricks', or 'none'
    labourers_present  INT NOT NULL,
    misc_expense       NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    misc_note          TEXT,
    is_corrected       VARCHAR(5) NOT NULL DEFAULT 'no'
);

-- ---------------------------------------------------------------------------
-- 7. Utility Bills — matches utility_bills.txt
--    One row per (month, bill_type) — a second entry for the same month
--    and type overwrites, same as enters_utility_bill() in the original.
-- ---------------------------------------------------------------------------
CREATE TABLE utility_bills (
    bill_id           SERIAL PRIMARY KEY,
    billing_month     VARCHAR(7) NOT NULL,   -- format: YYYY-MM
    bill_type         VARCHAR(20) NOT NULL,  -- 'Electricity' or 'Water'
    amount            NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    entry_date        DATE NOT NULL,
    entry_timestamp   TIME NOT NULL,
    CONSTRAINT unique_monthly_bill UNIQUE (billing_month, bill_type)
);

-- ---------------------------------------------------------------------------
-- 8. Settings — holds bricks_per_mix (was a loose bricks_per_mix.txt file,
--    default 182, matching DEFAULT_BRICKS_PER_MIX in shared_data.py)
-- ---------------------------------------------------------------------------
CREATE TABLE settings (
    setting_key   VARCHAR(50) PRIMARY KEY,
    setting_value NUMERIC(12,3) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 9. System Users — passwords are bcrypt hashes. User rows are intentionally
--    not seeded here; credentials must be supplied during provisioning.
-- ---------------------------------------------------------------------------
CREATE TABLE system_users (
    username        VARCHAR(50) PRIMARY KEY,
    password_hash   VARCHAR(100) NOT NULL,
    user_role       VARCHAR(20) NOT NULL  -- 'admin' or 'manager'
);

-- ===========================================================================
-- SEED DATA — same starting values as your original files
-- ===========================================================================

INSERT INTO materials_inventory (material_name, current_stock, unit_rate, unit_type) VALUES
('Flyash',   4000, 0.90,   'kg'),
('Sand',     2000, 1.10,   'kg'),
('Chemical', 260,  4.40,   'L'),
('Cement',   480,  309.00, 'packets');

INSERT INTO recipe (material_name, qty_per_mix) VALUES
('Flyash',   300),
('Sand',     200),
('Chemical', 12),
('Cement',   1);

INSERT INTO making_charges (charge_name, cost_per_brick) VALUES
('Labour',       0.80),
('Loading',      0.30),
('Union',        0.10),
('Salary_Other', 0.52);

INSERT INTO settings (setting_key, setting_value) VALUES
('bricks_per_mix', 182);

