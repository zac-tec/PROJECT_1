-- ===========================================================================
-- MIGRATION: Client WhatsApp Number (for the Daily Report share feature)
-- SAFE TO RUN on your existing database.
-- ===========================================================================

INSERT INTO settings (setting_key, setting_value)
VALUES ('client_whatsapp_number_placeholder', 0)
ON CONFLICT (setting_key) DO NOTHING;

-- The settings table only stores NUMERIC values, but a phone number needs
-- to stay as text (leading country code, no math ever done on it). Rather
-- than force a phone number into a numeric column, we use a tiny
-- dedicated table instead — cleaner than storing a WhatsApp number in a
-- table meant for numbers-you-calculate-with.
DELETE FROM settings WHERE setting_key = 'client_whatsapp_number_placeholder';

CREATE TABLE IF NOT EXISTS app_settings_text (
    setting_key   VARCHAR(50) PRIMARY KEY,
    setting_value TEXT NOT NULL
);

INSERT INTO app_settings_text (setting_key, setting_value)
VALUES ('client_whatsapp_number', '')
ON CONFLICT (setting_key) DO NOTHING;
