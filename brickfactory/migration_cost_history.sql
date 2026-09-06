SELECT pg_advisory_xact_lock(624019);

CREATE TABLE IF NOT EXISTS production_cost_snapshots (
    production_date DATE PRIMARY KEY REFERENCES production_log(production_date) ON DELETE CASCADE,
    mixes_run INT NOT NULL,
    bricks_made INT NOT NULL,
    material_cost_total NUMERIC(14,2) NOT NULL,
    making_cost_total NUMERIC(14,2) NOT NULL,
    material_cost_per_mix NUMERIC(14,4) NOT NULL,
    making_cost_per_brick NUMERIC(14,4) NOT NULL,
    rates JSONB NOT NULL,
    recipe JSONB NOT NULL,
    making_charges JSONB NOT NULL,
    bricks_per_mix NUMERIC(12,3) NOT NULL,
    snapshot_source TEXT NOT NULL CHECK (snapshot_source IN ('recorded', 'migration_baseline')),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_revision_history (
 id BIGSERIAL PRIMARY KEY,
 production_date DATE NOT NULL,
 previous_record JSONB NOT NULL,
 corrected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS monthly_overhead_versions (
 setting_key TEXT NOT NULL,
 effective_month VARCHAR(7) NOT NULL,
 amount NUMERIC(14,2) NOT NULL CHECK(amount>=0),
 PRIMARY KEY(setting_key,effective_month)
);
INSERT INTO monthly_overhead_versions(setting_key,effective_month,amount)
SELECT setting_key,'1900-01',setting_value FROM settings
WHERE setting_key IN ('rent_amount','manager_salary_amount','electricity_default','water_default')
ON CONFLICT DO NOTHING;

INSERT INTO production_cost_snapshots (
    production_date, mixes_run, bricks_made, material_cost_total, making_cost_total,
    material_cost_per_mix, making_cost_per_brick, rates, recipe, making_charges,
    bricks_per_mix, snapshot_source
)
SELECT p.production_date, p.mixes_run, p.bricks_made,
       ROUND((p.mixes_run * cfg.material_per_mix)::numeric, 2),
       ROUND((p.bricks_made * cfg.making_per_brick)::numeric, 2),
       cfg.material_per_mix, cfg.making_per_brick,
       cfg.rates, cfg.recipe, cfg.charges, cfg.bricks_per_mix,
       'migration_baseline'
FROM production_log p
CROSS JOIN LATERAL (
    SELECT
      (SELECT COALESCE(SUM(r.qty_per_mix * m.unit_rate), 0) FROM recipe r JOIN materials_inventory m USING(material_name)) AS material_per_mix,
      (SELECT COALESCE(SUM(cost_per_brick), 0) FROM making_charges) AS making_per_brick,
      (SELECT jsonb_object_agg(material_name, unit_rate) FROM materials_inventory) AS rates,
      (SELECT jsonb_object_agg(material_name, qty_per_mix) FROM recipe) AS recipe,
      (SELECT jsonb_object_agg(charge_name, cost_per_brick) FROM making_charges) AS charges,
      COALESCE((SELECT setting_value FROM settings WHERE setting_key='bricks_per_mix'), 182) AS bricks_per_mix
) cfg
ON CONFLICT (production_date) DO NOTHING;
