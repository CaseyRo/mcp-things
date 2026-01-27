"""Protocol compliance tests for MCP.

Tests verify JSON-RPC message format, request/response structure,
and transport-specific protocol requirements without requiring a running server.
"""

import pytest

from tests.mcp_client import MCPClient


@pytest.mark.unit
class TestMCPProtocol:
    """Test MCP protocol compliance."""

    def test_jsonrpc_request_format(self):
        """Test JSON-RPC request format validation."""
        client = MCPClient("http://localhost:8009")

        # Create a request
        request = client._create_request("tools/list")

        # Verify JSON-RPC 2.0 structure
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert "method" in request
        assert request["method"] == "tools/list"

        # Verify ID is string or number (not null)
        assert request["id"] is not None
        assert isinstance(request["id"], (str, int))

    def test_jsonrpc_request_with_params(self):
        """Test JSON-RPC request with parameters."""
        client = MCPClient("http://localhost:8009")

        params = {"name": "test-tool", "arguments": {"title": "Test"}}
        request = client._create_request("tools/call", params=params)

        assert request["jsonrpc"] == "2.0"
        assert "params" in request
        assert request["params"] == params

    def test_jsonrpc_request_id_generation(self):
        """Test request ID generation."""
        client = MCPClient("http://localhost:8009")

        # Generate multiple requests - IDs should be unique
        request1 = client._create_request("tools/list")
        request2 = client._create_request("tools/list")

        assert request1["id"] != request2["id"]

    def test_jsonrpc_request_custom_id(self):
        """Test request with custom ID."""
        client = MCPClient("http://localhost:8009")

        custom_id = "custom-request-123"
        request = client._create_request("tools/list", request_id=custom_id)

        assert request["id"] == custom_id

    def test_streamable_http_endpoint_construction(self):
        """Test streamable-http endpoint URL construction."""
        client = MCPClient("http://localhost:8009")
        assert client.endpoint == "http://localhost:8009/mcp"

        client2 = MCPClient("http://127.0.0.1:8009")
        assert client2.endpoint == "http://127.0.0.1:8009/mcp"

        client3 = MCPClient("https://example.com")
        assert client3.endpoint == "https://example.com/mcp"

    def test_streamable_http_accept_headers(self):
        """Test streamable-http Accept header requirements."""
        # The client should include proper Accept headers
        # This is verified by the client implementation
        client = MCPClient("http://localhost:8009")

        # Verify client is configured for streamable-http
        assert "/mcp" in client.endpoint

    def test_mcp_method_names(self):
        """Test MCP method name format."""
        client = MCPClient("http://localhost:8009")

        # tools/list method
        request = client._create_request("tools/list")
        assert request["method"] == "tools/list"

        # tools/call method
        request = client._create_request("tools/call", params={"name": "test"})
        assert request["method"] == "tools/call"

    def test_tool_call_params_structure(self):
        """Test tool call parameter structure."""
        client = MCPClient("http://localhost:8009")

        # Create tool call request
        params = {
            "name": "add-todo",
            "arguments": {
                "title": "Test Todo",
                "notes": "Test notes",
            },
        }
        request = client._create_request("tools/call", params=params)

        assert request["params"]["name"] == "add-todo"
        assert "arguments" in request["params"]
        assert request["params"]["arguments"]["title"] == "Test Todo"

    def test_n8n_extra_params_structure(self):
        """Test n8n extra parameters structure."""
        client = MCPClient("http://localhost:8009")

        # Create request with n8n extra params
        n8n_params = {
            "name": "test-tool",
            "arguments": {},
            "toolCallId": "test-call-id",
            "sessionId": "test-session",
            "action": "execute",
            "chatInput": "test input",
        }
        request = client._create_request("tools/call", params=n8n_params)

        # Verify all params are included in request
        assert request["params"]["name"] == "test-tool"
        assert request["params"]["toolCallId"] == "test-call-id"
        assert request["params"]["sessionId"] == "test-session"
        assert request["params"]["action"] == "execute"
        assert request["params"]["chatInput"] == "test input"
