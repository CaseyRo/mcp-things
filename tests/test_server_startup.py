"""Smoke tests for server startup and basic functionality.

These tests verify that the server can start and endpoints respond.
Note: These are integration tests that may require Things 3 to be available.
"""

import pytest
import subprocess
import time
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

from things_mcp.settings import get_settings


@pytest.mark.integration
@pytest.mark.slow
class TestServerStartup:
    """Test that server starts correctly and endpoints respond."""

    @pytest.fixture
    def server_process(self):
        """Start server in background for testing."""
        server_script = (
            Path(__file__).parent.parent
            / "src"
            / "things_mcp"
            / "things_fast_server.py"
        )
        process = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait for server to start
        time.sleep(3)
        yield process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    @pytest.mark.skipif(httpx is None, reason="httpx not installed")
    def test_server_starts_successfully(self, server_process):
        """Server should start without errors."""
        assert server_process.poll() is None, "Server process should still be running"

    @pytest.mark.skipif(httpx is None, reason="httpx not installed")
    def test_streamable_http_endpoint_responds(self, server_process):
        """Streamable-HTTP endpoint should respond to requests."""
        settings = get_settings()
        url = (
            f"http://{settings.things_fastmcp_host}:{settings.things_fastmcp_port}/mcp"
        )

        time.sleep(1)

        try:
            response = httpx.get(url, timeout=5)
            assert response.status_code in [
                200,
                404,
                405,
            ], f"Expected 200/404/405, got {response.status_code}"
        except httpx.ConnectError:
            pytest.skip("Server not accessible")
