"""Create or replace one bcrypt-backed application user.

Usage:
    python provision_user.py admin admin
    python provision_user.py manager manager

The password is requested without echoing it and is never stored in this
source tree or passed as a command-line argument.
"""

import getpass
import sys

from auth_utils import hash_password
from database import get_connection


VALID_ROLES = {"admin", "manager"}


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in VALID_ROLES:
        print("Usage: python provision_user.py USERNAME admin|manager")
        return 2

    username = sys.argv[1].strip()
    if not username or len(username) > 50:
        print("Username must contain 1-50 characters.")
        return 2

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not password or password != confirmation:
        print("Passwords are empty or do not match.")
        return 2

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO system_users (username, password_hash, user_role)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    user_role = EXCLUDED.user_role
                """,
                (username, hash_password(password), sys.argv[2]),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Provisioned user '{username}' with role '{sys.argv[2]}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())