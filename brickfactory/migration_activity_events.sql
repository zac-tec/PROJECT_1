BEGIN;
CREATE TABLE IF NOT EXISTS factory_activity_events (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('material_refill', 'utility_bill')),
    details JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS factory_activity_events_time_idx ON factory_activity_events (occurred_at);
COMMIT;
