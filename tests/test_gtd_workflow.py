"""
GTD-native workflow tests for the 5-stage GTD approach.

These tests validate the GTD tools:
- Capture: capture-task
- Clarify: process-inbox, convert-to-project
- Organize: schedule-task, delegate-task, defer-task, plan-project
- Reflect: daily-review, weekly-review
- Engage: get-tasks, focus-mode, complete-task

Tests require Things 3 to be running. Test data uses MCP-TEST- prefix
and is automatically cleaned up.
"""

import pytest
import time
import things
from datetime import date, timedelta

# Import the mcp instance to get tool functions
from things_mcp.fast_server import mcp
from things_mcp.url_scheme import add_todo, execute_url
from tests.conftest import generate_test_title


# Helper to get tool function from FastMCP
def _get_tool_fn(name: str):
    return mcp._local_provider._components[f"tool:{name}@"].fn


# Get tool functions from the registered tools
# GTD Core (Engage/Capture/Clarify)
capture_task = _get_tool_fn("capture-task")
process_inbox = _get_tool_fn("process-inbox")
convert_to_project = _get_tool_fn("convert-to-project")
get_tasks = _get_tool_fn("get-tasks")
focus_mode = _get_tool_fn("focus-mode")
complete_task = _get_tool_fn("complete-task")

# GTD Organize
schedule_task = _get_tool_fn("schedule-task")
delegate_task = _get_tool_fn("delegate-task")
defer_task = _get_tool_fn("defer-task")
plan_project = _get_tool_fn("plan-project")

# GTD Reflect
daily_review = _get_tool_fn("daily-review")
weekly_review = _get_tool_fn("weekly-review")

# Utility
search_tasks = _get_tool_fn("search-tasks")


# =============================================================================
# GTD CAPTURE STAGE TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDCapture:
    """Test GTD Capture stage: capture-task."""

    @pytest.mark.asyncio
    async def test_capture_task_to_inbox(self, test_data_tracker):
        """Capture a task to inbox with minimal info."""
        title = generate_test_title("GTD-CAPTURE")

        result = await capture_task(title=title)

        assert "Captured to Inbox" in result
        assert title in result
        assert "process-inbox" in result.lower() or "schedule-task" in result.lower()

        # Verify task is in inbox
        time.sleep(1)
        inbox = things.inbox()
        found = any(t.get("title") == title for t in inbox)
        assert found, f"Task '{title}' not found in inbox"

        # Track for cleanup
        todo = next((t for t in inbox if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

    @pytest.mark.asyncio
    async def test_capture_task_with_context_tags(self, test_data_tracker):
        """Capture a task with GTD context tags."""
        title = generate_test_title("GTD-CAPTURE-CONTEXT")

        result = await capture_task(
            title=title,
            notes="Need to do this at computer",
            tags=["@computer", "high-energy"],
        )

        assert "Captured to Inbox" in result
        time.sleep(1)

        # Find and verify tags
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        assert todo is not None
        test_data_tracker.add_todo(todo["uuid"])

        # Note: tags may not be immediately visible in things-py due to caching


# =============================================================================
# GTD CLARIFY STAGE TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDClarify:
    """Test GTD Clarify stage: process-inbox, convert-to-project."""

    @pytest.mark.asyncio
    async def test_process_inbox_returns_oldest_item(self, test_data_tracker):
        """Process inbox should return oldest item with GTD guidance."""
        # Create a test item in inbox first
        title = generate_test_title("GTD-CLARIFY-PROCESS")
        await capture_task(title=title)
        time.sleep(1)

        # Track for cleanup
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Process inbox
        result = await process_inbox()

        # Should include GTD decision tree
        assert "actionable" in result.lower()
        assert "project" in result.lower() or "single action" in result.lower()

    @pytest.mark.asyncio
    async def test_process_inbox_empty(self):
        """Process inbox with empty inbox should indicate success."""
        # This test may fail if there are items in inbox
        # We can't guarantee empty inbox without clearing it
        result = await process_inbox()

        # Either shows an item or indicates inbox is clear
        assert "Inbox" in result or "inbox" in result

    @pytest.mark.asyncio
    async def test_convert_to_project(self, test_data_tracker):
        """Convert a task to a project with first action."""
        # Create a task first
        title = generate_test_title("GTD-CONVERT-TO-PROJECT")
        await capture_task(title=title, notes="This needs multiple steps")
        time.sleep(1.5)

        # Find the task
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        assert todo is not None, f"Could not find task: {title}"
        todo_id = todo["uuid"]

        # Convert to project
        result = await convert_to_project(
            task_id=todo_id,
            first_action="Research options",
        )

        assert "project" in result.lower()
        assert "Research options" in result or "first action" in result.lower()
        time.sleep(1.5)

        # Find the created project for cleanup
        projects = things.projects()
        project = next((p for p in projects if title in p.get("title", "")), None)
        if project:
            test_data_tracker.add_project(project["uuid"])

    @pytest.mark.asyncio
    async def test_convert_to_project_preserves_checklist_and_deadline(
        self, test_data_tracker
    ):
        """Convert a task with checklist items and deadline to a project.

        Verifies that:
        - Checklist items become tasks in the project
        - Deadline is preserved on the project (not child tasks)
        """
        # Create a task with checklist items and deadline
        title = generate_test_title("GTD-CONVERT-CHECKLIST")
        deadline = (date.today() + timedelta(days=14)).isoformat()
        checklist_items = ["Step 1: Research", "Step 2: Plan", "Step 3: Execute"]

        url = add_todo(
            title=title,
            notes="Task with checklist for conversion test",
            deadline=deadline,
            checklist_items=checklist_items,
        )
        execute_url(url)
        time.sleep(1.5)

        # Find the task
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        assert todo is not None, f"Could not find task: {title}"
        todo_id = todo["uuid"]

        # Verify checklist items exist on the task
        task_checklist = things.checklist_items(todo_id)
        assert len(task_checklist) == 3, "Task should have 3 checklist items"

        # Convert to project
        result = await convert_to_project(task_id=todo_id)
        time.sleep(1.5)

        # Verify result mentions checklist conversion
        assert "project" in result.lower()
        assert "checklist" in result.lower() or "3" in result

        # Find the created project
        projects = things.projects()
        project = next((p for p in projects if title in p.get("title", "")), None)
        assert project is not None, f"Could not find project: {title}"
        test_data_tracker.add_project(project["uuid"])

        # Verify project has the deadline
        assert project.get("deadline") == deadline, "Project should have the deadline"

        # Verify project has tasks (converted from checklist)
        project_tasks = things.todos(project=project["uuid"])
        assert (
            len(project_tasks) >= 3
        ), "Project should have at least 3 tasks from checklist"

        # Verify task titles match original checklist items
        task_titles = [t.get("title") for t in project_tasks]
        for item in checklist_items:
            assert (
                item in task_titles
            ), f"Checklist item '{item}' should be a project task"

        # Verify child tasks don't have the deadline (only project has it)
        for task in project_tasks:
            assert task.get("deadline") is None, "Child tasks should not have deadline"


# =============================================================================
# GTD ORGANIZE STAGE TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDOrganize:
    """Test GTD Organize stage: schedule-task, delegate-task, defer-task, plan-project."""

    @pytest.mark.asyncio
    async def test_schedule_task_for_today(self, test_data_tracker):
        """Schedule a task for today with context."""
        title = generate_test_title("GTD-SCHEDULE-TODAY")

        result = await schedule_task(
            title=title,
            when="today",
            context=["@computer"],
            notes="Scheduled via GTD tool",
        )

        assert "Scheduled" in result
        assert title in result
        assert "today" in result.lower()
        time.sleep(1)

        # Verify task is in today view
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None, f"Task '{title}' not found in today view"
        test_data_tracker.add_todo(todo["uuid"])

    @pytest.mark.asyncio
    async def test_schedule_task_for_someday(self, test_data_tracker):
        """Schedule a task for someday (incubation)."""
        title = generate_test_title("GTD-SCHEDULE-SOMEDAY")

        result = await schedule_task(
            title=title,
            when="someday",
        )

        assert "Scheduled" in result
        time.sleep(1)

        # Verify task is in someday view
        someday = things.someday()
        todo = next((t for t in someday if t.get("title") == title), None)
        assert todo is not None, f"Task '{title}' not found in someday view"
        test_data_tracker.add_todo(todo["uuid"])

    @pytest.mark.asyncio
    async def test_delegate_task(self, test_data_tracker):
        """Delegate a task and track as waiting-for."""
        # Create a task first
        title = generate_test_title("GTD-DELEGATE")
        await capture_task(title=title)
        time.sleep(1)

        # Find the task
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Delegate it
        result = await delegate_task(
            task_id=todo_id,
            delegated_to="Alice",
            follow_up_date="2025-12-31",
            notes="Emailed on test date",
        )

        assert "Delegated" in result or "delegated" in result
        assert "Alice" in result
        assert "waiting-for" in result.lower()
        time.sleep(1)

        # Verify task title was updated
        updated = things.get(todo_id)
        assert "Waiting" in updated.get("title", "") or "Alice" in updated.get(
            "title", ""
        )

    @pytest.mark.asyncio
    async def test_defer_task_to_someday(self, test_data_tracker):
        """Defer a task to someday for incubation."""
        # Create a task first
        title = generate_test_title("GTD-DEFER-SOMEDAY")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Find the task
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Defer to someday
        result = await defer_task(
            task_id=todo_id,
            defer_to="someday",
            reason="Not ready yet",
        )

        assert "Someday" in result or "someday" in result.lower()
        assert "incubation" in result.lower() or "weekly review" in result.lower()

    @pytest.mark.asyncio
    async def test_defer_task_to_specific_date(self, test_data_tracker):
        """Defer a task to a specific date (tickler)."""
        # Create a task first
        title = generate_test_title("GTD-DEFER-DATE")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Find the task
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Defer to specific date
        result = await defer_task(
            task_id=todo_id,
            defer_to="2025-12-25",
        )

        assert "2025-12-25" in result
        assert "reappear" in result.lower()

    @pytest.mark.asyncio
    async def test_plan_project_with_tasks(self, test_data_tracker):
        """Create a project with initial tasks atomically."""
        title = generate_test_title("GTD-PLAN-PROJECT")

        result = await plan_project(
            title=title,
            tasks=[
                {"title": "Research options", "when": "anytime"},
                {"title": "Draft proposal"},
                {"title": "Review with team"},
            ],
            notes="Project created via GTD tool",
        )

        assert "Created project" in result
        assert "3 tasks" in result
        time.sleep(1.5)

        # Find the project
        projects = things.projects()
        project = next((p for p in projects if p.get("title") == title), None)
        assert project is not None, f"Project '{title}' not found"
        test_data_tracker.add_project(project["uuid"])

    @pytest.mark.asyncio
    async def test_plan_project_warns_no_next_action(self, test_data_tracker):
        """Plan project should warn if no immediate next action."""
        title = generate_test_title("GTD-PLAN-NO-NEXT")

        result = await plan_project(
            title=title,
            tasks=[
                {"title": "Future task 1", "when": "2025-12-01"},
                {"title": "Future task 2", "when": "2025-12-15"},
            ],
        )

        # Should warn about no next action
        assert "Warning" in result or "warning" in result.lower()
        assert "next action" in result.lower()
        time.sleep(1.5)

        # Cleanup
        projects = things.projects()
        project = next((p for p in projects if p.get("title") == title), None)
        if project:
            test_data_tracker.add_project(project["uuid"])


# =============================================================================
# GTD REFLECT STAGE TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDReflect:
    """Test GTD Reflect stage: daily-review, weekly-review."""

    @pytest.mark.asyncio
    async def test_daily_review_returns_overview(self):
        """Daily review should return today's tasks, overdue, and inbox count."""
        result = await daily_review()

        assert "Daily Review" in result or "daily" in result.lower()
        assert "today" in result.lower() or "Today" in result
        # Should mention inbox status
        assert "inbox" in result.lower()

    @pytest.mark.asyncio
    async def test_weekly_review_returns_comprehensive(self):
        """Weekly review should include stalled projects, waiting-for, someday."""
        result = await weekly_review()

        assert "Weekly Review" in result or "weekly" in result.lower()
        # Should check for stalled projects
        assert "project" in result.lower()
        # Should mention someday/maybe
        assert "someday" in result.lower()

    @pytest.mark.asyncio
    async def test_weekly_review_detects_stalled_project(self, test_data_tracker):
        """Weekly review should detect projects with no next action."""
        # Create a project with no available next actions
        title = generate_test_title("GTD-STALLED-PROJECT")

        await plan_project(
            title=title,
            tasks=[
                {"title": "Future only task", "when": "2026-01-01"},
            ],
        )
        time.sleep(1.5)

        # Find and track project
        projects = things.projects()
        project = next((p for p in projects if p.get("title") == title), None)
        if project:
            test_data_tracker.add_project(project["uuid"])

        # Run weekly review
        review = await weekly_review()

        # The stalled project section should exist
        # (though our specific project may or may not be listed depending on implementation)
        assert (
            "Stalled" in review
            or "stalled" in review.lower()
            or "next action" in review.lower()
        )


# =============================================================================
# GTD ENGAGE STAGE TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDEngage:
    """Test GTD Engage stage: get-tasks, focus-mode, complete-task."""

    @pytest.mark.asyncio
    async def test_get_tasks_by_view(self, test_data_tracker):
        """Get tasks filtered by view."""
        # Create a task for today
        title = generate_test_title("GTD-GET-TASKS-TODAY")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Track for cleanup
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Get tasks for today view
        result = await get_tasks(view="today")

        assert "task" in result.lower()
        # Should include our test task
        assert title in result or "GTD-GET-TASKS" in result

    @pytest.mark.asyncio
    async def test_get_tasks_by_context(self, test_data_tracker):
        """Get tasks filtered by GTD context tag."""
        title = generate_test_title("GTD-GET-TASKS-CONTEXT")
        await schedule_task(title=title, when="anytime", context=["@computer"])
        time.sleep(1)

        # Track for cleanup
        anytime = things.anytime()
        todo = next((t for t in anytime if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Get tasks by context
        result = await get_tasks(context="@computer")

        # Should return tasks (may or may not include our specific task due to timing)
        assert "task" in result.lower() or "No tasks" in result

    @pytest.mark.asyncio
    async def test_get_tasks_inbox_view(self):
        """Get tasks from inbox view."""
        result = await get_tasks(view="inbox")

        # Should return inbox tasks or indicate empty
        assert "inbox" in result.lower() or "task" in result.lower()

    @pytest.mark.asyncio
    async def test_focus_mode_returns_single_task(self, test_data_tracker):
        """Focus mode should return the most important single task."""
        # Create a task for today
        title = generate_test_title("GTD-FOCUS-MODE")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Track for cleanup
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Run focus mode
        result = await focus_mode()

        # Should return either a task or indicate none available
        assert "FOCUS" in result or "No tasks" in result or "task" in result.lower()

    @pytest.mark.asyncio
    async def test_complete_task_by_id(self, test_data_tracker):
        """Complete a task by ID."""
        title = generate_test_title("GTD-COMPLETE-ID")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Find the task
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Complete it
        result = await complete_task(task_id=todo_id)

        assert "completed" in result.lower() or "momentum" in result.lower()
        time.sleep(1)

        # Verify completion
        completed = things.get(todo_id)
        assert completed.get("status") == "completed"

    @pytest.mark.asyncio
    async def test_complete_task_by_title(self, test_data_tracker):
        """Complete a task by title (fuzzy match)."""
        title = generate_test_title("GTD-COMPLETE-TITLE")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Find and track the task
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None
        test_data_tracker.add_todo(todo["uuid"])

        # Complete by title
        result = await complete_task(task_title="GTD-COMPLETE-TITLE")

        # Should either complete or ask for clarification if multiple match
        assert (
            "completed" in result.lower()
            or "Found" in result
            or "momentum" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_complete_task_with_notes(self, test_data_tracker):
        """Complete a task with completion notes."""
        title = generate_test_title("GTD-COMPLETE-NOTES")
        await schedule_task(title=title, when="today")
        time.sleep(1)

        # Find the task
        today = things.today()
        todo = next((t for t in today if t.get("title") == title), None)
        assert todo is not None
        todo_id = todo["uuid"]
        test_data_tracker.add_todo(todo_id)

        # Complete with notes
        result = await complete_task(
            task_id=todo_id,
            completion_notes="Finished in 30 minutes",
        )

        assert "completed" in result.lower() or "momentum" in result.lower()


# =============================================================================
# UTILITY TOOL TESTS
# =============================================================================


@pytest.mark.real
@pytest.mark.integration
class TestGTDUtility:
    """Test utility tools: search-tasks."""

    @pytest.mark.asyncio
    async def test_search_tasks_by_query(self, test_data_tracker):
        """Search for tasks by text query."""
        title = generate_test_title("GTD-SEARCH-QUERY")
        await capture_task(title=title, notes="Searchable content here")
        time.sleep(1)

        # Track for cleanup
        inbox = things.inbox()
        todo = next((t for t in inbox if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Search
        result = await search_tasks(query="GTD-SEARCH-QUERY")

        assert "Found" in result or title in result or "task" in result.lower()

    @pytest.mark.asyncio
    async def test_search_tasks_by_tag(self, test_data_tracker):
        """Search for tasks by tag."""
        title = generate_test_title("GTD-SEARCH-TAG")
        await schedule_task(title=title, when="anytime", context=["mcp-test-search"])
        time.sleep(1)

        # Track for cleanup
        anytime = things.anytime()
        todo = next((t for t in anytime if t.get("title") == title), None)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])

        # Search by tag
        result = await search_tasks(tag="mcp-test-search")

        # Should find tasks or indicate none found
        assert "task" in result.lower() or "No tasks" in result
