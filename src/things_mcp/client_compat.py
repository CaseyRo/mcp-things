"""Client compatibility utilities for MCP transport protocols.

This module consolidates all client-specific compatibility patches for:
- Claude Desktop/n8n/ChatGPT: All use streamable-http transport

mcp>=2 accepts RFC 7231 wildcard Accept headers natively (the old
``_check_accept_headers`` monkeypatch is gone). Clients that send no Accept
header, or only one of the two required types, are still rejected with 406;
``AcceptHeaderFixMiddleware`` rewrites those before they reach the SDK.
"""

from typing import List

from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send


class AcceptHeaderFixMiddleware:
    """Rewrite missing, partial, or wildcard Accept headers to the explicit
    ``application/json, text/event-stream`` pair the MCP SDK requires."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            headers = list(scope.get("headers", []))

            # Find and fix Accept header
            new_headers = []
            accept_found = False
            for name, value in headers:
                if name.lower() == b"accept":
                    accept_found = True
                    accept_value = value.decode("utf-8", errors="ignore")
                    if "*/*" in accept_value or "application/*" in accept_value:
                        # Replace with explicit types the MCP SDK expects
                        value = b"application/json, text/event-stream"
                    elif (
                        "application/json" not in accept_value
                        or "text/event-stream" not in accept_value
                    ):
                        value = b"application/json, text/event-stream"
                new_headers.append((name, value))

            # If no Accept header at all, add one
            if not accept_found:
                new_headers.append((b"accept", b"application/json, text/event-stream"))

            scope = dict(scope)
            scope["headers"] = new_headers

        await self.app(scope, receive, send)


def get_streamable_http_middleware() -> List[Middleware]:
    """Get middleware list for streamable-http transport.

    Returns middleware configured for clients that use streamable-http
    (Claude Desktop, n8n) which may send wildcard Accept headers.

    Returns:
        List[Middleware]: Middleware to apply to streamable-http app.
    """
    return [Middleware(AcceptHeaderFixMiddleware)]
