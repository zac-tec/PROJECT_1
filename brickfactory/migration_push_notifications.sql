CREATE TABLE IF NOT EXISTS push_subscriptions (
 id BIGSERIAL PRIMARY KEY, endpoint TEXT UNIQUE NOT NULL,
 username TEXT NOT NULL, session_version INTEGER NOT NULL,
 p256dh TEXT NOT NULL, auth TEXT NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS push_deliveries (
 subscription_id BIGINT NOT NULL REFERENCES push_subscriptions(id) ON DELETE CASCADE,
 reminder_date DATE NOT NULL, slot INTEGER NOT NULL CHECK(slot IN (20,22)),
 status TEXT NOT NULL DEFAULT 'claimed', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(subscription_id,reminder_date,slot)
);
