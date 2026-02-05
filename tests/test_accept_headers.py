"""Unit tests for Accept header handling.

Tests Accept header patching and middleware for client compatibility.
"""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from things_mcp.client_compat import patch_accept_headers, AcceptHeaderFixMiddleware


@pytest.mark.unit
class TestAcceptHeaders:
    """Test Accept header patching and middleware."""

    def test_patch_applies_successfully(self):
        """Accept header patch should apply without errors."""
        result = patch_accept_headers()
        assert result is True, "Accept header patch should apply successfully"

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
