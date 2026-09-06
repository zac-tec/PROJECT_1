-- Preserve existing users while aligning legacy password storage with auth.
-- A legacy password_value column may contain plaintext and must be rehashed
-- with rehash_passwords.py before the application is allowed to serve login.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'system_users'
          AND column_name = 'password_value'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'system_users'
          AND column_name = 'password_hash'
    ) THEN
        ALTER TABLE system_users RENAME COLUMN password_value TO password_hash;
    END IF;
END $$;