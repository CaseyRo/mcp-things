"""Client compatibility utilities for MCP transport protocols.

This module consolidates all client-specific compatibility patches for:
- Claude Desktop/n8n/ChatGPT: All use streamable-http transport

The streamable-http transport requires patching the MCP SDK's Accept header
validation to support RFC 7231 wildcard Accept headers (e.g., "*/*").
"""

from typing import List

from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .logging_config import get_logger

logger = get_logger(__name__)


def patch_accept_headers() -> bool:
    """Monkey-patch MCP SDK to fix Accept header validation for streamable-http.

    The MCP SDK incorrectly rejects wildcard Accept headers (*/*, application/*)
    which are valid per RFC 7231. This patch makes the SDK accept wildcards.

    See: https://github.com/modelcontextprotocol/python-sdk/issues/1641
    PR #1948 will fix this upstream but is not yet merged.

    Returns:
        bool: True if patch was applied successfully, False otherwise.
    """
    try:
        from mcp.server import streamable_http

        def patched_check_accept_headers(self, request) -> tuple[bool, bool]:
            """Patched version that handles wildcard Accept headers per RFC 7231."""
            accept_header = request.headers.get("accept", "")

            accept_types = [
                media_type.strip().split(";")[0]  # Strip quality params
                for media_type in accept_header.split(",")
            ]

            # Check for explicit types or wildcards that match them
            has_json = any(
                t.startswith("application/json") or t == "*/*" or t == "application/*"
                for t in accept_types
            )
            has_sse = any(
                t.startswith("text/event-stream") or t == "*/*" or t == "text/*"
                for t in accept_types
            )

            # If no Accept header or empty, be permissive (accept anything)
            if not accept_header or accept_header.strip() == "":
                return True, True

            return has_json, has_sse

        streamable_http.StreamableHTTPServerTransport._check_accept_headers = (
            patched_check_accept_headers
        )
        logger.info(
            "Patched MCP SDK Accept header validation for wildcard support (RFC 7231)"
        )
        return True
    except Exception as e:
        logger.warning(f"Could not patch MCP SDK Accept header validation: {e}")
        return False


class AcceptHeaderFixMiddleware:
    """ASGI middleware fallback for Accept header fixes.

    Rewrites wildcard Accept headers to explicit types required by MCP SDK.
    This is a fallback in case the monkey-patch doesn't apply.
    """

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
