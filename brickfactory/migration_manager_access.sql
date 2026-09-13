ALTER TABLE system_users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS manager_access_audit (
 id BIGSERIAL PRIMARY KEY, changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 changed_by TEXT NOT NULL, previous_username TEXT NOT NULL,
 new_username TEXT NOT NULL, reason TEXT NOT NULL
);
