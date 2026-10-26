"""
security/http_guard.py — keep the local API local.

The agent listens on 127.0.0.1, but any web page you visit can still send
requests there. CORS only stops a page from *reading* responses; it does not
stop the request. This middleware closes the gaps:

  * Host check — only 127.0.0.1 / localhost / ::1 / tauri.localhost. Stops DNS
    rebinding, where a site points its own domain at 127.0.0.1 and then reads
    your data as "same-origin".
  * Origin check — a browser request (it always carries Origin on cross-site
    POSTs and WebSockets) must come from the AUTOMATA UI itself. Stops a page
    from triggering actions such as body-less POSTs or WebSocket subscriptions.
  * Fetch-metadata — `Sec-Fetch-Site: cross-site` without an allowed Origin is refused.
  * Body size limit — refuses oversized requests early.

Requests without Origin come from programs on this PC (curl, the tray menu), which
already run as the same user; they pass the Host check like before.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = frozenset({
    "http://localhost:1420", "http://localhost:5173", "http://127.0.0.1:5173",
    "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost",
    "http://localhost:8000", "http://127.0.0.1:8000",
})
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1", "tauri.localhost", "testserver"})
MAX_BODY_BYTES = 10 * 1024 * 1024


def _host_ok(host_header: str) -> bool:
    host = (host_header or "").strip().lower()
    if host.startswith("["):  # [::1]:8000
        host = host.split("]")[0] + "]"
    else:
        host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return host in ALLOWED_HOSTS


class LocalOnlyGuard:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        reason = None
        if not _host_ok(headers.get("host", "")):
            reason = "unexpected Host header"
        origin = headers.get("origin")
        if reason is None and origin and origin not in ALLOWED_ORIGINS and origin != "null":
            reason = f"origin {origin} is not allowed"
        if reason is None and origin == "null" and scope["type"] == "websocket":
            reason = "opaque origin"
        if reason is None and headers.get("sec-fetch-site") == "cross-site" and origin not in ALLOWED_ORIGINS:
            reason = "cross-site request"
        if reason is None and scope["type"] == "http":
            try:
                if int(headers.get("content-length") or 0) > MAX_BODY_BYTES:
                    await _reply(send, 413, "Request body too large")
                    return
            except ValueError:
                reason = "bad Content-Length"
        if reason is not None:
            logger.warning("http_guard: refused %s %s — %s", scope.get("method", "WS"), scope.get("path"), reason)
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await _reply(send, 403, "Forbidden: requests must come from the AUTOMATA app on this PC")
            return
        await self.app(scope, receive, send)


async def _reply(send: Any, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
