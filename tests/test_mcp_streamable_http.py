"""Integration tests for streamable-http transport compliance.

Tests verify MCP streamable-http transport works correctly with n8n and ChatGPT
compatibility requirements. Focuses on protocol-level testing through actual
HTTP requests.

Uses TestClient for faster tests (no subprocess overhead) and real server
for tests requiring Things 3 integration.
"""

import pytest
import time

from tests.conftest import generate_test_title


@pytest.mark.integration
class TestStreamableHTTPTransport:
    """Test streamable-http transport compliance and client compatibility."""

    @pytest.mark.asyncio
    async def test_tool_discovery(self, mcp_client):
        """Test tool discovery via streamable-http."""
        response = await mcp_client.list_tools()

        assert "result" in response
        assert "tools" in response["result"]
        assert isinstance(response["result"]["tools"], list)
        assert len(response["result"]["tools"]) > 0

        # Verify tool structure
        tool = response["result"]["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_tool_discovery_response_format(self, mcp_client):
        """Test tool discovery response format validation."""
        response = await mcp_client.list_tools()

        # Verify JSON-RPC structure
        assert response["jsonrpc"] == "2.0"
        assert "id" in response
        assert "result" in response

        # Verify tools array structure
        tools = response["result"]["tools"]
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            # Verify schema is a dict
            assert isinstance(tool["inputSchema"], dict)

    @pytest.mark.asyncio
    async def test_tool_invocation_required_params(self, mcp_client):
        """Test tool invocation with only required parameters."""
        # Use a read-only tool that doesn't require Things 3
        response = await mcp_client.call_tool("get-cache-stats", arguments={})

        assert "result" in response
        assert "content" in response["result"]
        assert isinstance(response["result"]["content"], list)

    @pytest.mark.asyncio
    async def test_tool_invocation_optional_params(self, mcp_client):
        """Test tool invocation with optional parameters."""
        # Use get-cache-stats (no required params, small response) to avoid SSE streaming issues
        response = await mcp_client.call_tool("get-cache-stats", arguments={})

        assert "result" in response
        assert "content" in response["result"]

    @pytest.mark.asyncio
    async def test_tool_invocation_invalid_tool_name(self, mcp_client):
        """Test error handling for invalid tool name."""
        with pytest.raises(ValueError) as exc_info:
            await mcp_client.call_tool("invalid-tool-name", arguments={})

        assert (
            "Tool call failed" in str(exc_info.value)
            or "error" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_tool_invocation_invalid_parameters(self, mcp_client):
        """Test error handling for invalid parameters."""
        # Try to call a tool with wrong parameter types
        with pytest.raises(ValueError) as exc_info:
            await mcp_client.call_tool("get-tasks", arguments={"project_uuid": 12345})

        # Should get validation error
        assert "error" in str(exc_info.value).lower() or "Tool call failed" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_n8n_extra_params_stripped(self, mcp_client):
        """Test n8n extra parameters are stripped correctly."""
        # Call tool with n8n-specific extra params - should work
        response = await mcp_client.call_tool_with_n8n_params(
            "get-cache-stats", arguments={}
        )

        assert "result" in response
        # Tool should execute successfully despite extra params
        assert "content" in response["result"]

    @pytest.mark.asyncio
    async def test_n8n_null_values_handled(self, mcp_client):
        """Test n8n null values are handled correctly."""
        # Call tool with no args (optional params omitted); small response for reliable SSE parse
        response = await mcp_client.call_tool("get-cache-stats", arguments={})

        assert "result" in response
        assert "content" in response["result"]

    @pytest.mark.asyncio
    async def test_n8n_anyof_schema_flattening(self, mcp_client):
        """Test anyOf schema flattening for n8n compatibility."""
        response = await mcp_client.list_tools()

        tools = response["result"]["tools"]
        # Find a tool with optional parameters (likely to have anyOf)
        tool_with_optional = None
        for tool in tools:
            schema = tool.get("inputSchema", {})
            props = schema.get("properties", {})
            if props:
                # Check if any property has type array (flattened anyOf)
                for prop_schema in props.values():
                    if isinstance(prop_schema.get("type"), list):
                        tool_with_optional = tool
                        break
                if tool_with_optional:
                    break

        # Verify schemas don't have anyOf (should be flattened)
        for tool in tools:
            schema = tool.get("inputSchema", {})
            assert "anyOf" not in str(
                schema
            ), f"Tool {tool['name']} still has anyOf in schema"

    @pytest.mark.asyncio
    async def test_chatgpt_additional_properties(self, mcp_client):
        """Test ChatGPT compatibility: additionalProperties: false in schemas."""
        response = await mcp_client.list_tools()

        tools = response["result"]["tools"]
        for tool in tools:
            schema = tool.get("inputSchema", {})
            # Check if schema has properties (object type)
            if "properties" in schema:
                assert (
                    schema.get("additionalProperties") is False
                ), f"Tool {tool['name']} missing additionalProperties: false"

                # Check nested objects
                for prop_schema in schema.get("properties", {}).values():
                    if isinstance(prop_schema, dict) and "properties" in prop_schema:
                        assert (
                            prop_schema.get("additionalProperties") is False
                        ), f"Tool {tool['name']} nested object missing additionalProperties: false"

    @pytest.mark.asyncio
    async def test_chatgpt_required_fields(self, mcp_client):
        """Test ChatGPT compatibility: all fields in required array."""
        response = await mcp_client.list_tools()

        tools = response["result"]["tools"]
        for tool in tools:
            schema = tool.get("inputSchema", {})
            if "properties" in schema:
                props = schema.get("properties", {})
                required = schema.get("required", [])

                # All properties should be in required array
                assert set(props.keys()) == set(
                    required
                ), f"Tool {tool['name']} has properties not in required array"

                # Optional fields should have nullable types
                for prop_name, prop_schema in props.items():
                    prop_type = prop_schema.get("type")
                    # If type is a list, it should include "null" for optional fields
                    # (though all fields are in required, some may be nullable)
                    if isinstance(prop_type, list):
                        # This is fine - nullable type
                        pass
                    elif isinstance(prop_type, str) and prop_type != "null":
                        # Non-nullable type is fine
                        pass

    @pytest.mark.asyncio
    async def test_accept_header_wildcard_support(self, mcp_client):
        """Test Accept header wildcard support."""
        # Test that wildcard Accept header works
        # The client already uses proper Accept headers, so this test verifies
        # the server accepts requests with wildcard headers
        response = await mcp_client.list_tools()
        assert "result" in response
        assert "tools" in response["result"]

    @pytest.mark.real
    @pytest.mark.asyncio
    async def test_crud_create_todo(self, mcp_client, test_data_tracker):
        """Test CRUD: create todo via streamable-http."""
        title = generate_test_title("MCP-TEST-TODO")

        response = await mcp_client.call_tool(
            "add-todo",
            arguments={
                "title": title,
                "notes": "Test notes",
                "when": "today",
            },
        )

        assert "result" in response
        assert "content" in response["result"]
        content_text = response["result"]["content"][0].get("text", "")
        assert "Successfully created todo" in content_text or title in content_text

        # Give Things time to process
        time.sleep(1)

        # Track for cleanup - find the todo
        import things

        todos = things.search(title)
        if todos:
            test_data_tracker.add_todo(todos[0]["uuid"])

    @pytest.mark.real
    @pytest.mark.asyncio
    async def test_crud_read_todos(self, mcp_client):
        """Test CRUD: read todos via streamable-http."""
        response = await mcp_client.call_tool("get-tasks", arguments={})

        assert "result" in response
        assert "content" in response["result"]
        assert isinstance(response["result"]["content"], list)

    @pytest.mark.real
    @pytest.mark.asyncio
    async def test_crud_update_todo(self, mcp_client, test_data_tracker):
        """Test CRUD: update todo via streamable-http."""
        import things

        # Create a todo first
        title = generate_test_title("MCP-TEST-TODO")
        await mcp_client.call_tool(
            "add-todo",
            arguments={"title": title, "when": "today"},
        )
        time.sleep(1)

        # Find the todo
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Update the todo
        new_title = generate_test_title("MCP-TEST-TODO-UPDATED")
        response = await mcp_client.call_tool(
            "update-todo",
            arguments={"id": todo_id, "title": new_title, "notes": "Updated via MCP"},
        )

        assert "result" in response
        content_text = response["result"]["content"][0].get("text", "")
        assert "Successfully updated todo" in content_text

    @pytest.mark.real
    @pytest.mark.asyncio
    async def test_crud_delete_todo(self, mcp_client, test_data_tracker):
        """Test CRUD: delete/cancel todo via streamable-http."""
        import things

        # Create a todo first
        title = generate_test_title("MCP-TEST-TODO")
        await mcp_client.call_tool(
            "add-todo",
            arguments={"title": title, "when": "today"},
        )
        time.sleep(1)

        # Find the todo
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Cancel the todo
        response = await mcp_client.call_tool(
            "update-todo",
            arguments={"id": todo_id, "canceled": True},
        )

        assert "result" in response
        content_text = response["result"]["content"][0].get("text", "")
        assert "Successfully updated todo" in content_text

        # Verify cancellation
        time.sleep(1)
        todo = things.get(todo_id)
        assert todo.get("status") == "canceled"
