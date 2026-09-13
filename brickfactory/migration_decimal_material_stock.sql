ALTER TABLE materials_inventory ALTER COLUMN current_stock TYPE NUMERIC(16,3) USING current_stock::numeric;
ALTER TABLE factory_activity_events DROP CONSTRAINT IF EXISTS factory_activity_events_event_type_check;
ALTER TABLE factory_activity_events ADD CONSTRAINT factory_activity_events_event_type_check CHECK(event_type IN ('material_refill','utility_bill','material_stock_estimate'));
