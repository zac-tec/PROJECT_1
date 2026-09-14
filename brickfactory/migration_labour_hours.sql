ALTER TABLE production_log ADD COLUMN IF NOT EXISTS labour_hours NUMERIC(10,2);
ALTER TABLE production_cost_snapshots ADD COLUMN IF NOT EXISTS labour_hours NUMERIC(10,2);
ALTER TABLE production_cost_snapshots ADD COLUMN IF NOT EXISTS labour_hourly_rate NUMERIC(10,2);
ALTER TABLE production_cost_snapshots ADD COLUMN IF NOT EXISTS labour_cost_total NUMERIC(14,2);
UPDATE historical_entry_session SET payload=jsonb_set(payload,'{historical_making_charges}',(SELECT jsonb_object_agg(charge_name,cost_per_brick) FROM making_charges)) WHERE NOT payload ? 'historical_making_charges';
DELETE FROM making_charges WHERE charge_name='Labour';
