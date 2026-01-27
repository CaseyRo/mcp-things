"""MCP Protocol Test Client.

A lightweight client for making real MCP protocol requests to test server compliance.
Implements streamable-http transport for testing n8n and ChatGPT compatibility.
"""

import uuid
from typing import Any, Dict, Optional

import httpx

from things_mcp.settings import get_settings


class MCPClient:
    """Lightweight MCP protocol client for testing.

    Implements streamable-http transport to make real protocol requests
    and verify server compliance with MCP specification.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        """Initialize MCP client.

        Args:
            base_url: Base URL of the MCP server (e.g., "http://localhost:8009")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/mcp"
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _create_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a JSON-RPC 2.0 request message.

        Args:
            method: MCP method name (e.g., "tools/list", "tools/call")
            params: Method parameters
            request_id: Optional request ID (generated if not provided)

        Returns:
            JSON-RPC request dictionary
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }

        if params:
            request["params"] = params

        return request

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and parse response.

        Args:
            request: JSON-RPC request dictionary

        Returns:
            JSON-RPC response dictionary

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If response is not valid JSON-RPC
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        response = await self.client.post(
            self.endpoint,
            json=request,
            headers=headers,
        )
        response.raise_for_status()

        result = response.json()

        # Validate JSON-RPC response format
        if "jsonrpc" not in result or result["jsonrpc"] != "2.0":
            raise ValueError(
                "Invalid JSON-RPC response: missing or invalid jsonrpc field"
            )

        if "id" not in result:
            raise ValueError("Invalid JSON-RPC response: missing id field")

        if result["id"] != request["id"]:
            raise ValueError(
                f"Response ID mismatch: expected {request['id']}, got {result['id']}"
            )

        return result

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools from the server.

        Returns:
            JSON-RPC response with tools list

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If response format is invalid
        """
        request = self._create_request("tools/list")
        response = await self._send_request(request)

        if "error" in response:
            raise ValueError(f"MCP error: {response['error']}")

        if "result" not in response:
            raise ValueError("Response missing result field")

        return response

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call a tool by name with arguments.

        Args:
            name: Tool name (e.g., "add-todo", "get-todos")
            arguments: Tool arguments dictionary
            request_id: Optional request ID

        Returns:
            JSON-RPC response with tool result

        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If response format is invalid or tool call failed
        """
        params = {"name": name}
        if arguments:
            params["arguments"] = arguments

        request = self._create_request(
            "tools/call", params=params, request_id=request_id
        )
        response = await self._send_request(request)

        if "error" in response:
            error = response["error"]
            raise ValueError(
                f"Tool call failed: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'unknown')})"
            )

        if "result" not in response:
            raise ValueError("Response missing result field")

        return response

    async def call_tool_with_n8n_params(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a tool with n8n-specific extra parameters to test compatibility.

        Args:
            name: Tool name
            arguments: Tool arguments dictionary

        Returns:
            JSON-RPC response with tool result

        Raises:
            ValueError: If tool call failed
        """
        # Add n8n-specific extra parameters that should be stripped
        n8n_params = {
            "name": name,
            "arguments": arguments or {},
            "toolCallId": "test-call-id-123",
            "sessionId": "test-session-456",
            "action": "execute",
            "chatInput": "test input",
        }

        request = self._create_request("tools/call", params=n8n_params)
        response = await self._send_request(request)

        if "error" in response:
            error = response["error"]
            raise ValueError(
                f"Tool call failed: {error.get('message', 'Unknown error')} "
                f"(code: {error.get('code', 'unknown')})"
            )

        if "result" not in response:
            raise ValueError("Response missing result field")

        return response


async def create_mcp_client(base_url: Optional[str] = None) -> MCPClient:
    """Create an MCP client with default settings.

    Args:
        base_url: Optional base URL (defaults to server settings)

    Returns:
        Configured MCPClient instance
    """
    if base_url is None:
        settings = get_settings()
        base_url = (
            f"http://{settings.things_fastmcp_host}:{settings.things_fastmcp_port}"
        )

    return MCPClient(base_url)
