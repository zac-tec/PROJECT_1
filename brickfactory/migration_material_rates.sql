SELECT pg_advisory_xact_lock(624021);

CREATE TABLE IF NOT EXISTS material_rate_versions (
    material_name VARCHAR(50) NOT NULL REFERENCES materials_inventory(material_name),
    effective_from DATE NOT NULL,
    unit_rate NUMERIC(12,2) NOT NULL CHECK (unit_rate >= 0),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT NOT NULL,
    PRIMARY KEY (material_name, effective_from)
);

INSERT INTO material_rate_versions (material_name, effective_from, unit_rate, changed_by)
SELECT material_name, DATE '1900-01-01', unit_rate, 'migration baseline'
FROM materials_inventory
ON CONFLICT (material_name, effective_from) DO NOTHING;

ALTER TABLE rate_history ADD COLUMN IF NOT EXISTS effective_from DATE;
UPDATE rate_history SET effective_from = change_date WHERE effective_from IS NULL;

