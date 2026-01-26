"""
Real integration tests for MCP workflow: create, edit, move, delete.

These tests require Things 3 to be running and will create/modify real data.
Test data is automatically cleaned up after each test.
"""

import pytest
import time
import things

# Import the mcp instance to get tool functions
from things_mcp.fast_server import mcp
from things_mcp.applescript_bridge import run_applescript
from tests.conftest import generate_test_title


# Helper to get tool function from FastMCP
def _get_tool_fn(name: str):
    return mcp._local_provider._components[f"tool:{name}@"].fn


# Get tool functions from the registered tools
add_task = _get_tool_fn("add-todo")
add_new_project = _get_tool_fn("add-project")
update_task = _get_tool_fn("update-todo")
search_todos = _get_tool_fn("search-todos")


@pytest.mark.real
@pytest.mark.integration
class TestMCPWorkflow:
    """Test the full MCP workflow: create -> edit -> move -> delete."""

    @pytest.mark.asyncio
    async def test_create_todo(self, test_data_tracker):
        """Test creating a todo via MCP."""
        title = generate_test_title("MCP-TEST-TODO")

        result = await add_task(
            title=title,
            notes="Test notes for MCP todo",
            when="today",
        )

        assert "Successfully created todo" in result
        assert title in result

        # Give Things time to process
        time.sleep(1)

        # Verify todo exists by searching
        search_result = await search_todos(title)
        assert title in search_result or "MCP-TEST-TODO" in search_result

    @pytest.mark.asyncio
    async def test_create_and_edit_todo(self, test_data_tracker):
        """Test creating and editing a todo via MCP."""
        # Create todo
        original_title = generate_test_title("MCP-TEST-TODO")

        result = await add_task(
            title=original_title,
            notes="Original notes",
        )
        assert "Successfully created todo" in result

        # Give Things time to process
        time.sleep(1)

        # Find the todo to get its ID
        todo = _find_todo_by_title_prefix("MCP-TEST-TODO")
        assert todo is not None, "Could not find todo with prefix MCP-TEST-TODO"

        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Edit the todo
        new_title = generate_test_title("MCP-TEST-TODO-EDITED")
        edit_result = await update_task(
            id=todo_id,
            title=new_title,
            notes="Updated notes via MCP",
            tags=["mcp-test-tag"],
        )

        assert "Successfully updated todo" in edit_result

        # Give Things time to process
        time.sleep(1)

        # Verify the edit
        updated_todo = things.get(todo_id)
        assert updated_todo is not None
        assert updated_todo["title"] == new_title
        assert "Updated notes via MCP" in updated_todo.get("notes", "")

    @pytest.mark.asyncio
    async def test_create_project_and_todo_in_project(self, test_data_tracker):
        """Test creating a project and adding a todo to it."""
        # Create project first
        project_title = generate_test_title("MCP-TEST-PROJECT")

        project_result = await add_new_project(
            title=project_title,
            notes="Test project for MCP workflow",
        )
        assert "Successfully created project" in project_result

        # Give Things time to process
        time.sleep(1.5)

        # Find the project to track it for cleanup
        project = _find_project_by_title(project_title)
        assert project is not None, f"Could not find created project: {project_title}"
        test_data_tracker.add_project(project["uuid"])

        # Create todo directly in the project using list_id (more reliable than list_title)
        todo_title = generate_test_title("MCP-TEST-TODO-INPROJ")
        todo_result = await add_task(
            title=todo_title,
            notes="Todo inside test project",
            list_id=project["uuid"],
        )
        assert "Successfully created todo" in todo_result

        # Give Things time to process
        time.sleep(1.5)

        # Verify todo is in the project (search by exact title)
        todo = _find_todo_by_title(todo_title)
        assert todo is not None, f"Could not find created todo: {todo_title}"
        test_data_tracker.add_todo(todo["uuid"])

        # Check if todo is associated with the project
        assert (
            todo.get("project") == project["uuid"]
        ), f"Todo not in project. Expected project={project['uuid']}, got project={todo.get('project')}"

    @pytest.mark.asyncio
    async def test_full_workflow_create_edit_move_delete(self, test_data_tracker):
        """
        Full MCP workflow test:
        1. Create a project
        2. Create a todo (in inbox)
        3. Edit the todo
        4. Move it to the project (via AppleScript - not supported by MCP)
        5. Delete/cancel the todo
        """
        # Step 1: Create a project
        project_title = generate_test_title("MCP-TEST-PROJECT-WORKFLOW")
        project_result = await add_new_project(title=project_title)
        assert "Successfully created project" in project_result
        time.sleep(1.5)

        project = _find_project_by_title(project_title)
        assert project is not None, f"Could not find created project: {project_title}"
        project_id = project["uuid"]
        test_data_tracker.add_project(project_id)

        # Step 2: Create a todo (goes to inbox by default)
        todo_title = generate_test_title("MCP-TEST-TODO-WORKFLOW")
        todo_result = await add_task(
            title=todo_title,
            notes="Initial notes",
        )
        assert "Successfully created todo" in todo_result
        time.sleep(1.5)

        todo = _find_todo_by_title(todo_title)
        assert todo is not None, f"Could not find created todo: {todo_title}"
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Step 3: Edit the todo
        updated_title = generate_test_title("MCP-WORKFLOW-UPDATED")
        edit_result = await update_task(
            id=todo_id,
            title=updated_title,
            notes="Updated notes in workflow test",
        )
        assert "Successfully updated todo" in edit_result
        time.sleep(1.5)

        # Verify edit worked
        updated_todo = things.get(todo_id)
        assert updated_todo["title"] == updated_title

        # Step 4: Move to project (via AppleScript - MCP update-todo doesn't support list_id)
        move_result = _move_todo_to_project_applescript(todo_id, project_id)
        assert move_result is True, "Failed to move todo to project via AppleScript"
        time.sleep(1.5)

        # Verify move worked
        moved_todo = things.get(todo_id)
        assert (
            moved_todo.get("project") == project_id
        ), f"Todo was not moved to project. Expected {project_id}, got {moved_todo.get('project')}"

        # Step 5: Delete (cancel) the todo via MCP
        delete_result = await update_task(
            id=todo_id,
            canceled=True,
        )
        assert "Successfully updated todo" in delete_result
        time.sleep(1)

        # Verify cancellation
        canceled_todo = things.get(todo_id)
        assert canceled_todo.get("status") == "canceled", "Todo was not canceled"

    @pytest.mark.asyncio
    async def test_complete_todo(self, test_data_tracker):
        """Test completing a todo via MCP."""
        # Create todo
        title = generate_test_title("MCP-TEST-TODO-COMPLETE")
        await add_task(title=title)
        time.sleep(1)

        todo = _find_todo_by_title_prefix("MCP-TEST-TODO-COMPLETE")
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Complete the todo
        result = await update_task(id=todo_id, completed=True)
        assert "Successfully updated todo" in result
        time.sleep(1)

        # Verify completion
        completed_todo = things.get(todo_id)
        assert completed_todo.get("status") == "completed"

    @pytest.mark.asyncio
    async def test_add_todo_with_full_options(self, test_data_tracker):
        """Test creating a todo with all available options."""
        title = generate_test_title("MCP-TEST-TODO-FULL")

        result = await add_task(
            title=title,
            notes="Full options test",
            when="tomorrow",
            deadline="2025-12-31",
            tags=["mcp-test", "full-options"],
            checklist_items=["Subtask 1", "Subtask 2", "Subtask 3"],
        )

        assert "Successfully created todo" in result
        time.sleep(1)

        todo = _find_todo_by_title_prefix("MCP-TEST-TODO-FULL")
        assert todo is not None
        test_data_tracker.add_todo(todo["uuid"])

        # Verify the todo has the expected properties
        assert todo["title"] == title
        assert "Full options test" in todo.get("notes", "")


# Helper functions


def _find_todo_by_title(title: str, max_retries: int = 3):
    """Find a todo by exact title using things-py.

    Uses multiple search strategies and retries to handle
    SQLite caching/timing issues.
    """
    for attempt in range(max_retries):
        # Strategy 1: Use search (most direct)
        search_results = things.search(title)
        for item in search_results:
            if item.get("type") == "to-do" and item.get("title") == title:
                return item

        # Strategy 2: Check inbox (new todos often go here)
        inbox_todos = things.inbox()
        for todo in inbox_todos:
            if todo.get("title") == title:
                return todo

        # Strategy 3: Check today
        today_todos = things.today()
        for todo in today_todos:
            if todo.get("title") == title:
                return todo

        # Strategy 4: Check upcoming (for scheduled todos)
        upcoming_todos = things.upcoming()
        for todo in upcoming_todos:
            if todo.get("title") == title:
                return todo

        # Strategy 5: Get all todos
        all_todos = things.todos(start=None)
        for todo in all_todos:
            if todo.get("title") == title:
                return todo

        # Wait before retry to allow Things to sync
        if attempt < max_retries - 1:
            time.sleep(0.5)

    return None


def _find_todo_by_title_prefix(prefix: str, max_retries: int = 3):
    """Find a todo by title prefix using things-py."""
    for attempt in range(max_retries):
        search_results = things.search(prefix)
        for item in search_results:
            if item.get("type") == "to-do" and item.get("title", "").startswith(prefix):
                return item

        inbox_todos = things.inbox()
        for todo in inbox_todos:
            if todo.get("title", "").startswith(prefix):
                return todo

        all_todos = things.todos(start=None)
        for todo in all_todos:
            if todo.get("title", "").startswith(prefix):
                return todo

        if attempt < max_retries - 1:
            time.sleep(0.5)

    return None


def _find_project_by_title(title: str, max_retries: int = 3):
    """Find a project by exact title using things-py."""
    for attempt in range(max_retries):
        # Strategy 1: Use search
        search_results = things.search(title)
        for item in search_results:
            if item.get("type") == "project" and item.get("title") == title:
                return item

        # Strategy 2: Direct projects list
        projects = things.projects()
        for project in projects:
            if project.get("title") == title:
                return project

        # Wait before retry
        if attempt < max_retries - 1:
            time.sleep(0.5)

    return None


def _find_project_by_title_prefix(prefix: str, max_retries: int = 3):
    """Find a project by title prefix using things-py."""
    for attempt in range(max_retries):
        search_results = things.search(prefix)
        for item in search_results:
            if item.get("type") == "project" and item.get("title", "").startswith(
                prefix
            ):
                return item

        projects = things.projects()
        for project in projects:
            if project.get("title", "").startswith(prefix):
                return project

        if attempt < max_retries - 1:
            time.sleep(0.5)

    return None


def _move_todo_to_project_applescript(todo_id: str, project_id: str) -> bool:
    """
    Move a todo to a project using AppleScript.

    This is needed because the MCP update-todo tool doesn't support
    changing the list/project of an existing todo.

    Note: Things 3 AppleScript doesn't support the 'move' command for todos.
    Instead, we set the 'project' property directly.
    """
    script = f"""tell application "Things3"
    set theTodo to to do id "{todo_id}"
    set theProject to project id "{project_id}"
    set project of theTodo to theProject
end tell"""

    result = run_applescript(script)
    return result is not False
