"""Unit tests for GTD tool functions using mocked Things library.

These tests exercise the tool logic (filtering, formatting, error handling)
without requiring Things 3 to be running.
"""

from pathlib import Path

import pytest
from unittest import mock
from fastmcp.exceptions import ToolError

from tests.conftest import create_mock_todo, create_mock_project


class TestGetTasks:
    """Test get-tasks tool with mocked Things data."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.get_tasks = mcp._local_provider._components["tool:get-tasks@"].fn

    @pytest.mark.asyncio
    async def test_inbox_view(self):
        self.things.inbox.return_value = [create_mock_todo(title="Buy milk")]
        result = await self.get_tasks(view="inbox")
        assert "Buy milk" in result
        assert "1 task" in result

    @pytest.mark.asyncio
    async def test_empty_inbox(self):
        self.things.inbox.return_value = []
        result = await self.get_tasks(view="inbox")
        assert "No tasks found" in result

    @pytest.mark.asyncio
    async def test_invalid_view(self):
        with pytest.raises(ToolError, match="Unknown view"):
            await self.get_tasks(view="nonexistent")

    @pytest.mark.asyncio
    async def test_context_filter(self):
        self.things.todos.return_value = [
            create_mock_todo(title="At desk", tags=["@computer"]),
            create_mock_todo(title="Out and about", tags=["@errands"]),
        ]
        result = await self.get_tasks(context="@computer")
        assert "At desk" in result
        assert "Out and about" not in result

    @pytest.mark.asyncio
    async def test_multiple_context_tags(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Task A", tags=["@computer"]),
            create_mock_todo(title="Task B", tags=["@phone"]),
            create_mock_todo(title="Task C", tags=["@office"]),
        ]
        result = await self.get_tasks(context=["@computer", "@phone"])
        assert "Task A" in result
        assert "Task B" in result
        assert "Task C" not in result

    @pytest.mark.asyncio
    async def test_today_view(self):
        self.things.today.return_value = [create_mock_todo(title="Today task")]
        result = await self.get_tasks(view="today")
        assert "Today task" in result

    @pytest.mark.asyncio
    async def test_someday_view(self):
        self.things.someday.return_value = [create_mock_todo(title="Someday task")]
        result = await self.get_tasks(view="someday")
        assert "Someday task" in result

    @pytest.mark.asyncio
    async def test_energy_filter(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Hard work", tags=["high-energy"]),
            create_mock_todo(title="Easy work", tags=["low-energy"]),
        ]
        result = await self.get_tasks(energy="high-energy")
        assert "Hard work" in result
        assert "Easy work" not in result


class TestFocusMode:
    """Test focus-mode tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.focus_mode = mcp._local_provider._components["tool:focus-mode@"].fn

    @pytest.mark.asyncio
    async def test_no_tasks_available(self):
        self.things.todos.return_value = []
        self.things.today.return_value = []
        self.things.anytime.return_value = []
        result = await self.focus_mode()
        assert "No tasks match" in result

    @pytest.mark.asyncio
    async def test_overdue_task_prioritized(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Overdue!", deadline="2020-01-01"),
        ]
        self.things.today.return_value = []
        self.things.anytime.return_value = []
        result = await self.focus_mode()
        assert "OVERDUE" in result
        assert "Overdue!" in result

    @pytest.mark.asyncio
    async def test_today_task_returned(self):
        self.things.todos.return_value = []
        self.things.today.return_value = [create_mock_todo(title="Do today")]
        self.things.anytime.return_value = []
        result = await self.focus_mode()
        assert "Do today" in result


class TestCompleteTask:
    """Test complete-task tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        monkeypatch.setattr(
            "things_mcp.tools_gtd_core.execute_url", mock.Mock(return_value=True)
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_core.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        from things_mcp.fast_server import mcp

        self.complete_task = mcp._local_provider._components["tool:complete-task@"].fn

    @pytest.mark.asyncio
    async def test_requires_id_or_title(self):
        with pytest.raises(ToolError, match="Provide either"):
            await self.complete_task()

    @pytest.mark.asyncio
    async def test_complete_by_id(self):
        self.things.get.return_value = create_mock_todo(uuid_str="abc123")
        result = await self.complete_task(task_id="abc123")
        assert "completed" in result.lower()

    @pytest.mark.asyncio
    async def test_title_search_no_match(self):
        self.things.todos.return_value = []
        result = await self.complete_task(task_title="nonexistent")
        assert "No task found" in result

    @pytest.mark.asyncio
    async def test_title_search_multiple_matches(self):
        self.things.todos.return_value = [
            create_mock_todo(uuid_str="a1", title="Buy groceries"),
            create_mock_todo(uuid_str="a2", title="Buy supplies"),
        ]
        result = await self.complete_task(task_title="Buy")
        assert "Found 2 tasks" in result
        assert "a1" in result
        assert "a2" in result


class TestCaptureTask:
    """Test capture-task tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        monkeypatch.setattr(
            "things_mcp.tools_gtd_core.execute_url", mock.Mock(return_value=True)
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_core.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_core.ensure_tags_exist", mock.Mock(return_value=True)
        )
        from things_mcp.fast_server import mcp

        self.capture_task = mcp._local_provider._components["tool:capture-task@"].fn

    @pytest.mark.asyncio
    async def test_basic_capture(self):
        result = await self.capture_task(title="New idea")
        assert "Captured to Inbox" in result
        assert "New idea" in result

    @pytest.mark.asyncio
    async def test_capture_with_tags(self):
        result = await self.capture_task(title="Phone call", tags=["@phone"])
        assert "Captured to Inbox" in result


class TestProcessInbox:
    """Test process-inbox tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.process_inbox = mcp._local_provider._components["tool:process-inbox@"].fn

    @pytest.mark.asyncio
    async def test_empty_inbox(self):
        self.things.inbox.return_value = []
        result = await self.process_inbox()
        assert "Inbox is clear" in result

    @pytest.mark.asyncio
    async def test_processes_oldest_item(self):
        self.things.inbox.return_value = [
            create_mock_todo(title="Oldest item"),
            create_mock_todo(title="Newer item"),
        ]
        result = await self.process_inbox()
        assert "Oldest item" in result
        assert "1 item remaining" in result
        assert "GTD Decision Tree" in result


class TestScheduleTask:
    """Test schedule-task tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", mock.Mock(return_value=True)
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.ensure_tags_exist",
            mock.Mock(return_value=True),
        )
        from things_mcp.fast_server import mcp

        self.schedule_task = mcp._local_provider._components["tool:schedule-task@"].fn

    @pytest.mark.asyncio
    async def test_schedule_for_today(self):
        result = await self.schedule_task(title="Do thing", when="today")
        assert "Scheduled" in result
        assert "today" in result

    @pytest.mark.asyncio
    async def test_schedule_with_deadline(self):
        result = await self.schedule_task(
            title="Urgent", when="today", deadline="2026-03-20"
        )
        assert "Deadline: 2026-03-20" in result


class TestDelegateTask:
    """Test delegate-task tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", mock.Mock(return_value=True)
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.ensure_tags_exist",
            mock.Mock(return_value=True),
        )
        from things_mcp.fast_server import mcp

        self.delegate_task = mcp._local_provider._components["tool:delegate-task@"].fn

    @pytest.mark.asyncio
    async def test_task_not_found(self):
        self.things.get.return_value = None
        with pytest.raises(ToolError, match="Task not found"):
            await self.delegate_task(task_id="bad-id", delegated_to="Alice")

    @pytest.mark.asyncio
    async def test_successful_delegation(self):
        self.things.get.return_value = create_mock_todo(
            uuid_str="task1", title="Review PR"
        )
        result = await self.delegate_task(task_id="task1", delegated_to="Alice")
        assert "Delegated to Alice" in result
        assert "waiting-for" in result


class TestResolveListId:
    """Test resolve_list_id helper."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things):
        self.things = mock_things
        from things_mcp.resolvers import resolve_list_id

        self.resolve = resolve_list_id

    def test_direct_uuid_lookup(self):
        self.things.get.return_value = create_mock_project(uuid_str="proj-123")
        assert self.resolve("proj-123", "project") == "proj-123"

    def test_name_lookup_single_match(self):
        self.things.get.return_value = None
        self.things.projects.return_value = [
            create_mock_project(uuid_str="p1", title="My Project")
        ]
        assert self.resolve("My Project", "project") == "p1"

    def test_name_lookup_multiple_matches(self):
        self.things.get.return_value = None
        self.things.projects.return_value = [
            create_mock_project(uuid_str="p1", title="Work"),
            create_mock_project(uuid_str="p2", title="Work"),
        ]
        with pytest.raises(ToolError, match="Multiple"):
            self.resolve("Work", "project")

    def test_name_lookup_no_match(self):
        self.things.get.return_value = None
        self.things.projects.return_value = []
        with pytest.raises(ToolError, match="not found"):
            self.resolve("Nonexistent", "project")


class TestDailyReview:
    """Test daily-review tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.daily_review = mcp._local_provider._components["tool:daily-review@"].fn

    @pytest.mark.asyncio
    async def test_empty_day(self):
        self.things.today.return_value = []
        self.things.inbox.return_value = []
        self.things.todos.return_value = []
        result = await self.daily_review()
        assert "Daily Review" in result
        assert "0 tasks today" in result

    @pytest.mark.asyncio
    async def test_with_overdue(self):
        self.things.today.return_value = []
        self.things.inbox.return_value = []
        self.things.todos.return_value = [
            create_mock_todo(title="Late task", deadline="2020-01-01"),
        ]
        result = await self.daily_review()
        assert "overdue" in result.lower()
        assert "Late task" in result


class TestSearchTasks:
    """Test search-tasks tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.search_tasks = mcp._local_provider._components["tool:search-tasks@"].fn

    @pytest.mark.asyncio
    async def test_requires_query_or_filter(self):
        with pytest.raises(ToolError, match="Provide query or at least one filter"):
            await self.search_tasks()

    @pytest.mark.asyncio
    async def test_search_by_query(self):
        self.things.search.return_value = [create_mock_todo(title="Found it")]
        result = await self.search_tasks(query="Found")
        assert "Found it" in result
        assert "1 task" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        self.things.search.return_value = []
        result = await self.search_tasks(query="nothing")
        assert "No tasks found" in result


class TestTriageInsights:
    """Test triage-insights tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        from things_mcp.triage_tracker import TriageTracker

        self.tracker = TriageTracker(history_file=Path("/dev/null"))
        monkeypatch.setattr("things_mcp.tools_utility.triage_tracker", self.tracker)
        from things_mcp.fast_server import mcp

        self.triage_insights = mcp._local_provider._components[
            "tool:triage-insights@"
        ].fn

    @pytest.mark.asyncio
    async def test_no_data(self):
        result = await self.triage_insights()
        assert "No triage activity" in result
