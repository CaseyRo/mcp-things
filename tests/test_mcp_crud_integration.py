"""End-to-end CRUD integration tests via MCP protocol.

Tests verify complete Create-Read-Update-Delete workflows work correctly
through actual MCP protocol calls using streamable-http transport.
"""

import pytest
import time
import things

from tests.conftest import generate_test_title


@pytest.mark.integration
@pytest.mark.real
class TestMCPCRUDIntegration:
    """Test complete CRUD workflows via MCP protocol."""

    @pytest.mark.asyncio
    async def test_complete_crud_workflow_streamable_http(
        self, mcp_client, test_data_tracker
    ):
        """Test complete CRUD workflow via streamable-http."""
        title = generate_test_title("MCP-TEST-TODO")

        # Create
        create_response = await mcp_client.call_tool(
            "add-todo",
            arguments={"title": title, "notes": "Initial notes", "when": "today"},
        )
        assert "result" in create_response
        content_text = create_response["result"]["content"][0].get("text", "")
        assert "Successfully created todo" in content_text or title in content_text

        time.sleep(1)

        # Find and track for cleanup
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Read
        read_response = await mcp_client.call_tool("get-todos", arguments={})
        assert "result" in read_response
        assert "content" in read_response["result"]

        # Update
        updated_title = generate_test_title("MCP-TEST-TODO-UPDATED")
        update_response = await mcp_client.call_tool(
            "update-todo",
            arguments={"id": todo_id, "title": updated_title, "notes": "Updated notes"},
        )
        assert "result" in update_response
        content_text = update_response["result"]["content"][0].get("text", "")
        assert "Successfully updated todo" in content_text

        time.sleep(1)

        # Verify update
        updated_todo = things.get(todo_id)
        assert updated_todo["title"] == updated_title

        # Delete (cancel)
        delete_response = await mcp_client.call_tool(
            "update-todo", arguments={"id": todo_id, "canceled": True}
        )
        assert "result" in delete_response

        time.sleep(1)

        # Verify deletion
        canceled_todo = things.get(todo_id)
        assert canceled_todo.get("status") == "canceled"

    @pytest.mark.asyncio
    async def test_n8n_crud_workflow(self, mcp_client, test_data_tracker):
        """Test CRUD workflow with n8n compatibility (extra params)."""
        title = generate_test_title("MCP-TEST-TODO")

        # Create with n8n-style extra params
        create_response = await mcp_client.call_tool_with_n8n_params(
            "add-todo",
            arguments={"title": title, "when": "today"},
        )
        assert "result" in create_response

        time.sleep(1)

        # Find and track
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Read
        read_response = await mcp_client.call_tool("get-todos", arguments={})
        assert "result" in read_response

        # Update with n8n params
        updated_title = generate_test_title("MCP-TEST-TODO-N8N")
        update_response = await mcp_client.call_tool_with_n8n_params(
            "update-todo",
            arguments={"id": todo_id, "title": updated_title},
        )
        assert "result" in update_response

        time.sleep(1)

        # Verify update worked
        updated_todo = things.get(todo_id)
        assert updated_todo["title"] == updated_title

    @pytest.mark.asyncio
    async def test_chatgpt_crud_workflow(self, mcp_client, test_data_tracker):
        """Test CRUD workflow with ChatGPT schema requirements."""
        title = generate_test_title("MCP-TEST-TODO")

        # Create - ChatGPT schemas require all fields, nullable for optional
        create_response = await mcp_client.call_tool(
            "add-todo",
            arguments={
                "title": title,
                "notes": None,  # Explicit null for optional field
                "when": "today",
                "deadline": None,
                "tags": None,
            },
        )
        assert "result" in create_response

        time.sleep(1)

        # Find and track
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Read
        read_response = await mcp_client.call_tool("get-todos", arguments={})
        assert "result" in read_response

        # Update with explicit nulls
        updated_title = generate_test_title("MCP-TEST-TODO-CHATGPT")
        update_response = await mcp_client.call_tool(
            "update-todo",
            arguments={
                "id": todo_id,
                "title": updated_title,
                "notes": None,  # Explicit null
            },
        )
        assert "result" in update_response

        time.sleep(1)

        # Verify update
        updated_todo = things.get(todo_id)
        assert updated_todo["title"] == updated_title

    @pytest.mark.asyncio
    async def test_project_crud_workflow(self, mcp_client, test_data_tracker):
        """Test project CRUD workflow."""
        project_title = generate_test_title("MCP-TEST-PROJECT")

        # Create project
        create_response = await mcp_client.call_tool(
            "add-project",
            arguments={"title": project_title, "notes": "Test project"},
        )
        assert "result" in create_response

        time.sleep(1.5)

        # Find and track
        projects = things.search(project_title)
        assert len(projects) > 0
        project_id = projects[0]["uuid"]
        test_data_tracker.add_project(project_id)

        # Read project
        read_response = await mcp_client.call_tool(
            "get-projects", arguments={"include_items": False}
        )
        assert "result" in read_response

        # Update project
        updated_title = generate_test_title("MCP-TEST-PROJECT-UPDATED")
        update_response = await mcp_client.call_tool(
            "update-project",
            arguments={"id": project_id, "title": updated_title},
        )
        assert "result" in update_response

        time.sleep(1)

        # Verify update
        updated_project = things.get(project_id)
        assert updated_project["title"] == updated_title

    @pytest.mark.asyncio
    async def test_error_recovery(self, mcp_client):
        """Test error recovery: invalid operation → retry with correct params."""
        # Try invalid tool name
        with pytest.raises(ValueError):
            await mcp_client.call_tool("invalid-tool", arguments={})

        # Retry with correct tool name
        response = await mcp_client.call_tool("get-cache-stats", arguments={})
        assert "result" in response

    @pytest.mark.asyncio
    async def test_data_integrity(self, mcp_client, test_data_tracker):
        """Test data integrity: create → read → verify data matches."""
        title = generate_test_title("MCP-TEST-TODO")
        notes = "Test notes for integrity check"

        # Create
        await mcp_client.call_tool(
            "add-todo",
            arguments={"title": title, "notes": notes, "when": "today"},
        )

        time.sleep(1)

        # Find and track
        todos = things.search(title)
        assert len(todos) > 0
        todo_id = todos[0]["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Read via MCP
        read_response = await mcp_client.call_tool("get-todos", arguments={})
        assert "result" in read_response

        # Verify data matches
        todo = things.get(todo_id)
        assert todo["title"] == title
        assert notes in todo.get("notes", "")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mcp_client):
        """Test concurrent tool calls."""
        import asyncio

        # Make multiple concurrent read-only calls
        tasks = [
            mcp_client.call_tool("get-cache-stats", arguments={}),
            mcp_client.call_tool("get-projects", arguments={"include_items": False}),
            mcp_client.call_tool("get-areas", arguments={"include_items": False}),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert "result" in result
