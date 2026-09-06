-- ===========================================================================
-- MIGRATION: Replace Salary_Other per-brick charge with proper Fixed
-- Monthly Overhead (Rent, Manager Salary, Electricity default, Water default)
-- SAFE TO RUN on your existing database.
-- ===========================================================================

-- Remove the flawed 0.52-per-brick charge. History rows for it are left
-- alone (making_charges_history) as a historical record — only the live
-- charges table row is removed, so it stops being used in calculations.
DELETE FROM making_charges WHERE charge_name = 'Salary_Other';

-- New fixed monthly overhead settings (admin-editable). Electricity/Water
-- here are only FALLBACK defaults — if the manager has already entered an
-- actual bill for a given month via Utility Bills, that real value is
-- always used instead of these defaults.
INSERT INTO settings (setting_key, setting_value) VALUES
    ('rent_amount', 25000),
    ('manager_salary_amount', 30000),
    ('electricity_default', 12000),
    ('water_default', 6000)
ON CONFLICT (setting_key) DO NOTHING;
