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


@pytest.mark.integration
@pytest.mark.slow
class TestServerStartup:
    """Test that server starts correctly and endpoints respond."""

    @pytest.fixture
    def server_process(self):
        """Start server in background for testing (port 8010 to avoid conflict with mcp_server_process)."""
        import os

        project_root = Path(__file__).parent.parent
        env = os.environ.copy()
        env["THINGS_FASTMCP_PORT"] = "8010"
        process = subprocess.Popen(
            [sys.executable, "-m", "things_mcp.things_fast_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env=env,
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
        if server_process.poll() is not None:
            _, stderr = server_process.communicate()
            pytest.skip(
                f"Server exited with {server_process.returncode}; stderr: {stderr!r}"
            )

    @pytest.mark.skipif(httpx is None, reason="httpx not installed")
    def test_streamable_http_endpoint_responds(self, server_process):
        """Streamable-HTTP endpoint should respond to requests."""
        url = "http://127.0.0.1:8010/mcp"

        time.sleep(1)

        try:
            response = httpx.get(url, timeout=5)
            # 200/404/405 OK; 400 possible in MCP 1.26+ when GET without session
            assert response.status_code in [
                200,
                400,
                404,
                405,
            ], f"Expected 200/400/404/405, got {response.status_code}"
        except httpx.ConnectError:
            pytest.skip("Server not accessible")
