"""
REHASH PASSWORDS (run this once)
Converts the plaintext passwords currently sitting in system_users into
real bcrypt hashes. Safe to run more than once (it just re-hashes
whatever's there — but running it TWICE would hash an already-hashed
value and break login, so this script checks first and refuses to touch
a value that already looks like a bcrypt hash).

Usage:
    python rehash_passwords.py

Run this AFTER migration_password_hash.sql, and BEFORE trying
to log in again — between those two steps, login will not work.
"""

from database import get_connection
from auth_utils import hash_password


def looks_already_hashed(value: str) -> bool:
    """Bcrypt hashes always start with $2b$ (or $2a$/$2y$ on older versions)."""
    return value.startswith("$2b$") or value.startswith("$2a$") or value.startswith("$2y$")


def main():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username, password_hash FROM system_users")
        users = cursor.fetchall()

        for user in users:
            username = user["username"]
            current_value = user["password_hash"]

            if looks_already_hashed(current_value):
                print(f"Skipping '{username}' — already looks hashed.")
                continue

            new_hash = hash_password(current_value)
            cursor.execute(
                "UPDATE system_users SET password_hash = %s WHERE username = %s",
                (new_hash, username),
            )
            print(f"Hashed password for '{username}'.")

        conn.commit()
        cursor.close()
        print("\nDone. Existing plaintext passwords still work for login (the ACTUAL")
        print("password text didn't change) — only how it's stored did.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
