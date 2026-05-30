"""Unit tests for GTD tool functions using mocked Things library.

These tests exercise the tool logic (filtering, formatting, error handling)
without requiring Things 3 to be running.
"""

from pathlib import Path

import pytest
from unittest import mock
from fastmcp.exceptions import ToolError

from tests.conftest import create_mock_todo, create_mock_project, tool_text


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
        text = tool_text(result)
        assert "Buy milk" in text
        assert "1 task" in text

    @pytest.mark.asyncio
    async def test_empty_inbox(self):
        self.things.inbox.return_value = []
        result = await self.get_tasks(view="inbox")
        assert "No tasks found" in tool_text(result)

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
        text = tool_text(result)
        assert "At desk" in text
        assert "Out and about" not in text

    @pytest.mark.asyncio
    async def test_multiple_context_tags(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Task A", tags=["@computer"]),
            create_mock_todo(title="Task B", tags=["@phone"]),
            create_mock_todo(title="Task C", tags=["@office"]),
        ]
        result = await self.get_tasks(context=["@computer", "@phone"])
        text = tool_text(result)
        assert "Task A" in text
        assert "Task B" in text
        assert "Task C" not in text

    @pytest.mark.asyncio
    async def test_today_view(self):
        self.things.today.return_value = [create_mock_todo(title="Today task")]
        result = await self.get_tasks(view="today")
        assert "Today task" in tool_text(result)

    @pytest.mark.asyncio
    async def test_someday_view(self):
        self.things.someday.return_value = [create_mock_todo(title="Someday task")]
        result = await self.get_tasks(view="someday")
        assert "Someday task" in tool_text(result)

    @pytest.mark.asyncio
    async def test_energy_filter(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Hard work", tags=["high-energy"]),
            create_mock_todo(title="Easy work", tags=["low-energy"]),
        ]
        result = await self.get_tasks(energy="high-energy")
        text = tool_text(result)
        assert "Hard work" in text
        assert "Easy work" not in text

    @pytest.mark.asyncio
    async def test_structured_content_shape(self):
        """Verify structured payload carries full Things metadata per CDI-1021."""
        self.things.today.return_value = [
            create_mock_todo(
                uuid_str="abc-123",
                title="Buy milk",
                tags=["@errands", "5min"],
                deadline="2026-05-01",
                project="proj-1",
            ),
        ]
        result = await self.get_tasks(view="today")

        # ToolResult, not a string.
        assert hasattr(result, "structured_content")
        envelope = result.structured_content
        assert envelope is not None

        # Three-field envelope.
        assert set(envelope.keys()) == {"data", "summary", "meta"}

        data = envelope["data"]
        assert isinstance(data, list)
        assert len(data) == 1

        todo = data[0]
        assert todo["uuid"] == "abc-123"
        assert todo["title"] == "Buy milk"
        assert todo["type"] == "to-do"
        assert todo["tags"] == ["@errands", "5min"]
        assert todo["deadline"] == "2026-05-01"
        assert todo["project"] == "proj-1"
        # Optional fields serialise as null, not missing.
        assert "notes" in todo
        assert "area" in todo

        # Meta carries counts.
        assert envelope["meta"]["total_count"] == 1
        assert envelope["meta"]["shown"] == 1
        assert "truncated" not in envelope["meta"]

    @pytest.mark.asyncio
    async def test_structured_content_truncation(self):
        """When results exceed limit, meta.truncated is set."""
        self.things.todos.return_value = [
            create_mock_todo(uuid_str=f"id-{i}", title=f"Task {i}") for i in range(5)
        ]
        result = await self.get_tasks(limit=2)
        envelope = result.structured_content
        assert envelope["meta"]["total_count"] == 5
        assert envelope["meta"]["shown"] == 2
        assert envelope["meta"]["truncated"] is True
        assert len(envelope["data"]) == 2

    @pytest.mark.asyncio
    async def test_empty_envelope_shape(self):
        """Empty results still produce a valid envelope with data: []."""
        self.things.inbox.return_value = []
        result = await self.get_tasks(view="inbox")
        envelope = result.structured_content
        assert envelope["data"] == []
        assert "No tasks found" in envelope["summary"]


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
        assert "No tasks match" in tool_text(result)

    @pytest.mark.asyncio
    async def test_overdue_task_prioritized(self):
        self.things.todos.return_value = [
            create_mock_todo(title="Overdue!", deadline="2020-01-01"),
        ]
        self.things.today.return_value = []
        self.things.anytime.return_value = []
        result = await self.focus_mode()
        text = tool_text(result)
        assert "OVERDUE" in text
        assert "Overdue!" in text
        envelope = result.structured_content
        assert envelope["data"]["selection_reason"] == "overdue"
        assert envelope["data"]["task"]["title"] == "Overdue!"

    @pytest.mark.asyncio
    async def test_today_task_returned(self):
        self.things.todos.return_value = []
        self.things.today.return_value = [create_mock_todo(title="Do today")]
        self.things.anytime.return_value = []
        result = await self.focus_mode()
        assert "Do today" in tool_text(result)


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
        text = tool_text(result)
        assert "completed" in text.lower()
        envelope = result.structured_content
        assert envelope["data"]["acknowledged"] is True
        assert envelope["data"]["thing_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_title_search_no_match(self):
        self.things.todos.return_value = []
        result = await self.complete_task(task_title="nonexistent")
        text = tool_text(result)
        assert "No task found" in text
        envelope = result.structured_content
        assert envelope["data"]["acknowledged"] is False

    @pytest.mark.asyncio
    async def test_title_search_multiple_matches(self):
        self.things.todos.return_value = [
            create_mock_todo(uuid_str="a1", title="Buy groceries"),
            create_mock_todo(uuid_str="a2", title="Buy supplies"),
        ]
        result = await self.complete_task(task_title="Buy")
        text = tool_text(result)
        assert "Found 2 tasks" in text
        assert "a1" in text
        assert "a2" in text


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
        text = tool_text(result)
        assert "Captured to Inbox" in text
        assert "New idea" in text
        envelope = result.structured_content
        assert envelope["data"]["acknowledged"] is True
        assert envelope["data"]["summary"].startswith("Captured to Inbox")

    @pytest.mark.asyncio
    async def test_capture_with_tags(self):
        result = await self.capture_task(title="Phone call", tags=["@phone"])
        assert "Captured to Inbox" in tool_text(result)


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
        text = tool_text(result)
        assert "Inbox is clear" in text
        envelope = result.structured_content
        assert envelope["meta"]["remaining"] == 0

    @pytest.mark.asyncio
    async def test_processes_oldest_item(self):
        self.things.inbox.return_value = [
            create_mock_todo(uuid_str="oldest-id", title="Oldest item"),
            create_mock_todo(title="Newer item"),
        ]
        self.things.checklist_items.return_value = []
        result = await self.process_inbox()
        text = tool_text(result)
        assert "Oldest item" in text
        assert "1 item remaining" in text
        assert "GTD Decision Tree" in text
        envelope = result.structured_content
        assert envelope["data"]["uuid"] == "oldest-id"
        assert envelope["data"]["title"] == "Oldest item"
        assert envelope["meta"]["remaining"] == 1


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
        text = tool_text(result)
        assert "Scheduled" in text
        assert "today" in text
        envelope = result.structured_content
        assert envelope["data"]["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_schedule_with_deadline(self):
        result = await self.schedule_task(
            title="Urgent", when="today", deadline="2026-03-20"
        )
        assert "Deadline: 2026-03-20" in tool_text(result)


class TestModifyTaskClearDates:
    """Test modify-task clearing of deadline / when (CDI-1167)."""

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
        # Capture the exact kwargs handed to the URL builder. We record into an
        # instance dict via side_effect (rather than reading call_args) so the
        # assertion is robust against any shared-mock / ordering effects.
        self.captured = {}

        def _capture(**kwargs):
            self.captured = dict(kwargs)
            return "things:///update?id=x"

        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.update_todo",
            mock.Mock(side_effect=_capture),
        )
        from things_mcp.fast_server import mcp

        self.modify_task = mcp._local_provider._components["tool:modify-task@"].fn

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sentinel", ["none", "clear", "remove", "null", "NONE", " Clear "]
    )
    async def test_clear_deadline_via_sentinel(self, sentinel):
        await self.modify_task(task_id="abc", deadline=sentinel)
        assert self.captured["deadline"] == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sentinel", ["none", "clear", "remove", "null"])
    async def test_clear_when_via_sentinel(self, sentinel):
        await self.modify_task(task_id="abc", when=sentinel)
        assert self.captured["when"] == ""

    @pytest.mark.asyncio
    async def test_someday_plus_clear_deadline_one_call(self):
        await self.modify_task(task_id="abc", when="someday", deadline="none")
        assert self.captured["when"] == "someday"
        assert self.captured["deadline"] == ""

    @pytest.mark.asyncio
    async def test_real_deadline_passes_through(self):
        await self.modify_task(task_id="abc", deadline="2026-06-01")
        assert self.captured["deadline"] == "2026-06-01"

    @pytest.mark.asyncio
    async def test_unset_dates_pass_through_as_none(self):
        await self.modify_task(task_id="abc", title="Renamed")
        assert self.captured["deadline"] is None
        assert self.captured["when"] is None


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
        text = tool_text(result)
        assert "Delegated to Alice" in text
        assert "waiting-for" in text
        envelope = result.structured_content
        assert envelope["data"]["thing_id"] == "task1"


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
        text = tool_text(result)
        assert "Daily Review" in text
        assert "0 tasks today" in text

    @pytest.mark.asyncio
    async def test_with_overdue(self):
        self.things.today.return_value = []
        self.things.inbox.return_value = []
        self.things.todos.return_value = [
            create_mock_todo(title="Late task", deadline="2020-01-01"),
        ]
        result = await self.daily_review()
        text = tool_text(result)
        assert "overdue" in text.lower()
        assert "Late task" in text
        envelope = result.structured_content
        assert envelope["data"]["period"] == "daily"
        assert len(envelope["data"]["overdue"]) == 1


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
        text = tool_text(result)
        assert "Found it" in text
        assert "1 task" in text

    @pytest.mark.asyncio
    async def test_no_results(self):
        self.things.search.return_value = []
        result = await self.search_tasks(query="nothing")
        assert "No tasks found" in tool_text(result)


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
        assert "No triage activity" in tool_text(result)
