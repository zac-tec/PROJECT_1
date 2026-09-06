"""
AUTH UTILS
Two jobs:
  1. Password hashing — turns a plaintext password into a one-way scrambled
     version (bcrypt) that's stored in the database instead of the real
     password. Verifying a login just re-scrambles the typed password the
     same way and checks if it matches — the real password is never stored
     or recoverable, even by someone with full database access.
  2. JWT tokens — the "wristband." create_access_token() is called once at
     login. decode_access_token() is called on every subsequent request to
     check the wristband is real and hasn't expired.
"""

import os
import datetime
import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12  # wristband expires after 12 hours — long enough for a full shift


def hash_password(plain_password: str) -> str:
    """Called once when creating/resetting a user's password."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Called at login — True if the typed password matches the stored hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(username: str, role: str) -> str:
    """Called once at successful login — this IS the wristband."""
    expire_at = datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"username": username, "role": role, "exp": expire_at}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Called on every protected request. Returns the payload (username, role)
    if the token is valid and not expired, or None if it's fake/expired/tampered.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
