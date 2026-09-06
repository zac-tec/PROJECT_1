"""
DEPENDENCIES (Route Guards)
FastAPI's mechanism for "check something before running this route" is
called a Dependency. These three are used like this in a router file:

    from dependencies import require_admin
    router = APIRouter(dependencies=[Depends(require_admin)])

That one line makes EVERY route in that file require a valid admin
wristband — if the check fails, FastAPI stops and returns an error
BEFORE any of your actual route code runs.

For files where only SOME routes need a specific role, apply it per-route
instead:

    @router.get("/something", dependencies=[Depends(require_admin)])
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth_utils import decode_access_token

# Tells FastAPI to look for "Authorization: Bearer <token>" on incoming
# requests, and auto-generates the padlock icons you'll see in /docs.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """
    The base check: is there a valid, non-expired token at all?
    Returns {"username": ..., "role": ...} if yes.
    Used directly on routes that any logged-in user (either role) can access.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Please sign in.", headers={"WWW-Authenticate": "Bearer"})
    token = credentials.credentials
    payload = decode_access_token(token)
    if not isinstance(payload, dict) or not isinstance(payload.get("username"), str) or not payload["username"].strip() or payload.get("role") not in {"admin", "manager"} or "exp" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        )
    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Base check, PLUS must be the admin role."""
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an admin account.",
        )
    return user


def require_manager(user: dict = Depends(get_current_user)) -> dict:
    """Base check, PLUS must be the manager role."""
    if user["role"] != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a manager account.",
        )
    return user
