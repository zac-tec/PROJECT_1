"""Focused ASGI tests; no startup migrations, emails or business writes."""
import asyncio
import json
import datetime

import jwt
from fastapi import HTTPException
import main
from auth_utils import JWT_SECRET, JWT_ALGORITHM, create_access_token


class Cursor:
    def close(self): pass


class Connection:
    def cursor(self): return Cursor()
    def close(self): pass


main.get_connection = Connection
main.get_stock = lambda cursor: {"Flyash": 123}


@main.app.get("/__test_error")
def raw_error():
    raise HTTPException(status_code=500, detail="PRIVATE_DATABASE_PASSWORD sql connection details")


@main.app.get("/__test_exception")
def unexpected_error():
    raise RuntimeError("PRIVATE_DATABASE_PASSWORD")


async def request(path, token=None, origin=None, method="GET", preflight=False):
    headers = []
    if token: headers.append((b"authorization", ("Bearer " + token).encode()))
    if origin: headers.append((b"origin", origin.encode()))
    if preflight:
        headers.extend([(b"access-control-request-method", b"GET"), (b"access-control-request-headers", b"authorization")])
    scope = {"type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1", "method":method,
             "scheme":"http", "path":path, "raw_path":path.encode(), "query_string":b"",
             "root_path":"", "headers":headers, "server":("test",80), "client":("127.0.0.1",123)}
    messages = []
    async def receive(): return {"type":"http.request", "body":b"", "more_body":False}
    async def send(message): messages.append(message)
    try: await main.app(scope, receive, send)
    except RuntimeError:
        if not messages: raise
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body


async def test():
    assert (await request("/stock"))[0] == 401
    assert (await request("/stock", "invalid"))[0] == 401
    for role in ("admin", "manager"):
        response = await request("/stock", create_access_token("test", role))
        assert response[0] == 200 and json.loads(response[2])["Flyash"]["quantity"] == 123
    for payload in ({"username":"test", "role":"admin"},
                    {"username":"test", "role":"unexpected", "exp":datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)},
                    {"username":"test", "role":"admin", "exp":1}):
        assert (await request("/stock", jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)))[0] == 401
    assert (await request("/rates", create_access_token("test", "manager")))[0] == 403
    assert (await request("/manager/stock", create_access_token("test", "admin")))[0] == 403
    allowed = await request("/stock", origin="https://vps.tailc0d72c.ts.net", method="OPTIONS", preflight=True)
    denied = await request("/stock", origin="https://untrusted.example", method="OPTIONS", preflight=True)
    assert allowed[0] == 200 and allowed[1][b"access-control-allow-origin"] == b"https://vps.tailc0d72c.ts.net"
    assert b"access-control-allow-credentials" not in allowed[1]
    assert denied[0] == 400 and b"access-control-allow-origin" not in denied[1]
    for path in ("/__test_error", "/__test_exception"):
        response = await request(path)
        assert response[0] == 500 and b"PRIVATE" not in response[2]
        assert json.loads(response[2])["detail"] == "Unable to complete this request. Please try again later."
    print("PASS: stock auth, both roles, malformed/expired claims, role isolation, CORS, safe 500 errors")


if __name__ == "__main__": asyncio.run(test())
