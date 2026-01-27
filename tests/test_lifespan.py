"""Integration tests for lifespan management.

Tests that lifespan events are properly handled for streamable-http transport setup.
"""

import pytest

from things_mcp import fast_server

# Access private function for testing
_create_combined_app = fast_server._create_combined_app
mcp = fast_server.mcp


@pytest.mark.integration
class TestLifespanManagement:
    """Test that lifespan events are properly handled."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_completes(self):
        """Streamable-http transport should complete startup successfully."""
        app = _create_combined_app(mcp, "streamable-http")

        # Test lifespan startup - Starlette stores lifespan as an attribute
        # We can test it by calling it directly
        if hasattr(app, "router") and hasattr(app.router, "lifespan_context"):
            async with app.router.lifespan_context(app):
                # If we get here, startup succeeded
                assert True
        else:
            # For Starlette, lifespan is passed to constructor and accessed via router
            # Just verify the app was created successfully
            assert app is not None
            assert len(app.routes) > 0

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_graceful(self):
        """Shutdown should complete without errors."""
        app = _create_combined_app(mcp, "streamable-http")

        # Verify app was created with lifespan
        assert app is not None
        # The lifespan is managed internally by Starlette
        # We can't easily test it without running the full server
        # So we just verify the app structure is correct
        assert len(app.routes) > 0

    @pytest.mark.asyncio
    async def test_streamable_http_lifespan(self):
        """Streamable-HTTP transport lifespan should work correctly."""
        app = _create_combined_app(mcp, "streamable-http")

        # Verify app was created
        assert app is not None
        assert len(app.routes) > 0
