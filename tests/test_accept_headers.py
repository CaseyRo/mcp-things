"""Unit tests for Accept header handling.

Tests Accept header patching and middleware for client compatibility.
"""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from things_mcp import fast_server
from things_mcp.client_compat import AcceptHeaderFixMiddleware


@pytest.mark.unit
class TestAcceptHeaders:
    """Test Accept header patching and middleware."""

    @pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
    @pytest.mark.parametrize(
        "accept",
        [None, "*/*", "application/json", "text/event-stream", "application/*"],
    )
    def test_real_app_serves_problematic_accept_headers(self, path, accept):
        """End to end: the mounted MCP app answers tools/list for Accept
        headers the SDK alone would 406 (missing / single-type), on both the
        bare and trailing-slash path."""
        app = fast_server._create_combined_app(fast_server.mcp, "streamable-http")
        headers = {
            "content-type": "application/json",
            "mcp-protocol-version": "2025-06-18",
            "authorization": f"Bearer {fast_server.mcp.auth._api_key}",
        }
        if accept is not None:
            headers["accept"] = accept
        with TestClient(app) as client:
            if accept is None:
                client.headers.pop("accept", None)
            r = client.post(
                path,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        assert '"tools"' in r.text

    def test_middleware_rewrites_wildcards(self):
        """Middleware should rewrite wildcard Accept headers."""
        app = Starlette()
        app.add_middleware(AcceptHeaderFixMiddleware)

        async def test_route(request):
            accept = request.headers.get("accept", "")
            return JSONResponse({"accept": accept})

        app.add_route("/test", test_route)

        client = TestClient(app)
        response = client.get("/test", headers={"accept": "*/*"})
        assert response.status_code == 200
        accept_header = response.json()["accept"]
        assert (
            "application/json" in accept_header or "text/event-stream" in accept_header
        )

    def test_middleware_adds_missing_accept(self):
        """Middleware should add Accept header if missing."""
        app = Starlette()
        app.add_middleware(AcceptHeaderFixMiddleware)

        async def test_route(request):
            accept = request.headers.get("accept", "")
            return JSONResponse({"accept": accept})

        app.add_route("/test", test_route)

        client = TestClient(app)
        response = client.get("/test")  # No Accept header
        assert response.status_code == 200
        accept_header = response.json()["accept"]
        assert (
            "application/json" in accept_header or "text/event-stream" in accept_header
        )

    def test_middleware_preserves_explicit_headers(self):
        """Middleware should preserve explicit Accept headers that are valid."""
        app = Starlette()
        app.add_middleware(AcceptHeaderFixMiddleware)

        async def test_route(request):
            accept = request.headers.get("accept", "")
            return JSONResponse({"accept": accept})

        app.add_route("/test", test_route)

        client = TestClient(app)
        response = client.get(
            "/test", headers={"accept": "application/json, text/event-stream"}
        )
        assert response.status_code == 200
        accept_header = response.json()["accept"]
        assert "application/json" in accept_header
        assert "text/event-stream" in accept_header
