"""
AUTH ROUTES
Login now does two real things it didn't before:
  1. Checks the password against a bcrypt HASH, not plaintext
  2. Issues a real JWT token (the "wristband") on success

This file being updated is only half the picture — see dependencies.py
for the guards that actually CHECK the wristband on every other route.
Without those, a valid login here still wouldn't stop someone from
calling the API directly. Both pieces are needed together.
"""

from fastapi import APIRouter, HTTPException
from database import get_connection
from schemas import LoginRequest, LoginResponse
from auth_utils import verify_password, create_access_token

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash, user_role FROM system_users WHERE username = %s",
            (body.username,),
        )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        conn.close()

    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    token = create_access_token(username=body.username, role=row["user_role"])
    return LoginResponse(access_token=token, username=body.username, role=row["user_role"])
