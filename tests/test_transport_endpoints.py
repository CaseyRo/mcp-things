"""Unit tests for transport endpoint configuration.

Tests that streamable-http transport is correctly configured.
"""

import pytest
from starlette.routing import Mount

from things_mcp import fast_server

# Access private function for testing
_create_combined_app = fast_server._create_combined_app
mcp = fast_server.mcp


@pytest.mark.unit
class TestTransportEndpoints:
    """Test that transport endpoints are correctly configured."""

    def test_streamable_http_endpoint_created_when_enabled(self):
        """Streamable-HTTP endpoint should exist when transport='streamable-http'."""
        app = _create_combined_app(mcp, "streamable-http")
        # Verify /mcp route exists
        routes = [route for route in app.routes if isinstance(route, Mount)]
        http_routes = [r for r in routes if r.path == "/mcp"]
        assert (
            len(http_routes) == 1
        ), "Streamable-HTTP endpoint should be created when transport='streamable-http'"

    def test_single_transport_endpoint_exists(self):
        """Only streamable-http endpoint should exist."""
        app = _create_combined_app(mcp, "streamable-http")
        routes = [route for route in app.routes if isinstance(route, Mount)]
        route_paths = [r.path for r in routes]
        assert "/mcp" in route_paths, "Streamable-HTTP endpoint should exist"
        assert "/sse" not in route_paths, "SSE endpoint should not exist"
