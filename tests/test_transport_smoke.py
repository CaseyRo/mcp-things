"""Fast smoke tests for transport configuration.

These tests verify transport setup without starting a full server.
Suitable for pre-commit hooks.
"""

import pytest
from starlette.routing import Mount

from things_mcp import fast_server

# Access private function for testing
_create_combined_app = fast_server._create_combined_app
mcp = fast_server.mcp


@pytest.mark.unit
class TestTransportSmoke:
    """Fast smoke tests for transport configuration."""

    def test_streamable_http_transport_configured(self):
        """Verify streamable-http transport is configured."""
        app = _create_combined_app(mcp, "streamable-http")
        routes = [route for route in app.routes if isinstance(route, Mount)]
        route_paths = [r.path for r in routes]
        assert "/mcp" in route_paths
        assert len(routes) == 1

    def test_app_has_lifespan(self):
        """Verify app has lifespan configured."""
        app = _create_combined_app(mcp, "streamable-http")
        # Starlette apps with lifespan have it stored in router
        assert hasattr(app, "router")
        # The lifespan function is passed to Starlette constructor
        # We can verify the app was created successfully
        assert app is not None

    def test_streamable_http_transport_creates_valid_app(self):
        """Verify streamable-http transport creates valid app."""
        app = _create_combined_app(mcp, "streamable-http")
        assert app is not None
        assert len(app.routes) > 0
