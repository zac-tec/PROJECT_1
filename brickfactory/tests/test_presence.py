"""No database, startup jobs or email calls; exercises actual ASGI guards."""
import asyncio
import json
from unittest.mock import patch
from fastapi import FastAPI
from auth_utils import create_access_token
from routers import presence

app = FastAPI()
app.include_router(presence.router)


async def request(path, method="GET", token=None):
    messages = []
    headers = [(b"authorization", ("Bearer " + token).encode())] if token else []
    scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
                 method=method, scheme="http", path=path, raw_path=path.encode(),
                 query_string=b"", root_path="", headers=headers,
                 server=("test", 80), client=("127.0.0.1", 123))
    async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message): messages.append(message)
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages)
    return start["status"], dict(start["headers"]), json.loads(body) if body else None


async def test():
    presence._users.clear()
    admin = create_access_token("owner", "admin")
    manager = create_access_token("<script>example</script>", "manager")
    assert (await request("/presence/heartbeat", "POST"))[0] == 401
    assert (await request("/presence/active"))[0] == 401
    assert (await request("/presence/active", token=manager))[0] == 403
    assert (await request("/presence/heartbeat", "POST", "invalid"))[0] == 401
    with patch.object(presence, "monotonic", return_value=100):
        assert (await request("/presence/heartbeat", "POST", manager))[0] == 204
        await request("/presence/heartbeat", "POST", manager)
        await request("/presence/heartbeat", "POST", admin)
        status, headers, data = await request("/presence/active", token=admin)
        assert status == 200 and data["count"] == 2
        assert headers[b"cache-control"] == b"no-store"
        assert {u["role"] for u in data["users"]} == {"admin", "manager"}
    with patch.object(presence, "monotonic", return_value=400):
        assert (await request("/presence/active", token=admin))[2]["count"] == 0
    print("PASS: auth, admin-only visibility, account deduplication, no-store and expiry")


if __name__ == "__main__": asyncio.run(test())
