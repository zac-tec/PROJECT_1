"""Ephemeral presence for the deployment's single Uvicorn worker.

Counts accounts with a visible app in the last five minutes, not sessions.
Nothing is written to the business database. Restarting clears the list.
"""
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, Response
from dependencies import get_current_user, require_admin

router = APIRouter(prefix="/presence", tags=["presence"])
WINDOW_SECONDS = 300
_users = {}
_lock = Lock()


def _prune(now):
    for name in list(_users):
        if now - _users[name][0] >= WINDOW_SECONDS:
            del _users[name]


@router.post("/heartbeat", status_code=204)
def heartbeat(user: dict = Depends(get_current_user)):
    now = monotonic()
    with _lock:
        _prune(now)
        _users[user["username"]] = (now, {
            "username": user["username"],
            "role": user["role"],
            "last_seen": datetime.now(timezone.utc).isoformat(),
        })
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/active")
def active_users(response: Response, user: dict = Depends(require_admin)):
    response.headers["Cache-Control"] = "no-store"
    with _lock:
        _prune(monotonic())
        users = sorted((dict(v[1]) for v in _users.values()), key=lambda u: u["last_seen"], reverse=True)
    return {"count": len(users), "window_seconds": WINDOW_SECONDS, "users": users}
