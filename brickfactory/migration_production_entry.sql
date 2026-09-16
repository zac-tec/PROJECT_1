CREATE TABLE IF NOT EXISTS production_submission_audit (
 id BIGSERIAL PRIMARY KEY,
 production_date DATE NOT NULL,
 entered_by TEXT NOT NULL,
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 entry_data JSONB NOT NULL
);
INSERT INTO app_settings_text(setting_key,setting_value)
VALUES('manager_production_backdate_days','1') ON CONFLICT DO NOTHING;
