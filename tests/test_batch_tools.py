"""Unit tests for batch tools (bulk-capture, bulk-complete, bulk-cancel, bulk-modify, bulk-triage).

Tests cover:
- CaptureItem and TriageDecision Pydantic model validation
- bulk-capture: JSON URL scheme building and execution
- bulk-complete: AppleScript UUID loop for completion
- bulk-cancel: AppleScript UUID loop for cancellation
- bulk-modify: URL scheme updates with mutual exclusivity checks
- bulk-triage: grouped action processing (AppleScript + URL scheme)
"""

import pytest
from unittest import mock
from pydantic import ValidationError
from fastmcp.exceptions import ToolError

from things_mcp.tools_batch import CaptureItem, TriageDecision
from tests.conftest import create_mock_todo


# ============================================================================
# Helpers
# ============================================================================


def _get_tool(mcp, name):
    """Get a tool function from the MCP server."""
    return mcp._local_provider._components[f"tool:{name}@"].fn


# ============================================================================
# 1. CaptureItem model tests
# ============================================================================


class TestCaptureItemModel:
    @pytest.mark.unit
    def test_valid_minimal(self):
        item = CaptureItem(title="Buy milk")
        assert item.title == "Buy milk"
        assert item.notes is None
        assert item.when is None
        assert item.tags is None
        assert item.deadline is None

    @pytest.mark.unit
    def test_valid_full(self):
        item = CaptureItem(
            title="Buy milk",
            notes="From the store",
            when="today",
            tags=["@errands"],
            deadline="2026-04-01",
        )
        assert item.title == "Buy milk"
        assert item.notes == "From the store"
        assert item.when == "today"
        assert item.tags == ["@errands"]
        assert item.deadline == "2026-04-01"

    @pytest.mark.unit
    def test_valid_when_values(self):
        for when_val in ["today", "tomorrow", "evening", "anytime", "someday"]:
            item = CaptureItem(title="Test", when=when_val)
            assert item.when == when_val

    @pytest.mark.unit
    def test_invalid_when_value(self):
        with pytest.raises(ValidationError):
            CaptureItem(title="Test", when="next-week")

    @pytest.mark.unit
    def test_missing_title(self):
        with pytest.raises(ValidationError):
            CaptureItem()


# ============================================================================
# 2. TriageDecision model tests
# ============================================================================


class TestTriageDecisionModel:
    @pytest.mark.unit
    def test_complete_valid(self):
        d = TriageDecision(task_id="test-uuid-001", action="complete")
        assert d.action == "complete"

    @pytest.mark.unit
    def test_cancel_valid(self):
        d = TriageDecision(task_id="test-uuid-001", action="cancel")
        assert d.action == "cancel"

    @pytest.mark.unit
    def test_defer_requires_when(self):
        with pytest.raises(ValidationError, match="when"):
            TriageDecision(task_id="test-uuid-001", action="defer")

    @pytest.mark.unit
    def test_defer_with_when(self):
        d = TriageDecision(task_id="test-uuid-001", action="defer", when="someday")
        assert d.when == "someday"

    @pytest.mark.unit
    def test_schedule_requires_when(self):
        with pytest.raises(ValidationError, match="when"):
            TriageDecision(task_id="test-uuid-001", action="schedule")

    @pytest.mark.unit
    def test_schedule_with_when(self):
        d = TriageDecision(task_id="test-uuid-001", action="schedule", when="tomorrow")
        assert d.when == "tomorrow"

    @pytest.mark.unit
    def test_delegate_requires_delegated_to(self):
        with pytest.raises(ValidationError, match="delegated_to"):
            TriageDecision(task_id="test-uuid-001", action="delegate")

    @pytest.mark.unit
    def test_delegate_with_delegated_to(self):
        d = TriageDecision(
            task_id="test-uuid-001", action="delegate", delegated_to="Alice"
        )
        assert d.delegated_to == "Alice"

    @pytest.mark.unit
    def test_assign_requires_project(self):
        with pytest.raises(ValidationError, match="project"):
            TriageDecision(task_id="test-uuid-001", action="assign")

    @pytest.mark.unit
    def test_assign_with_project(self):
        d = TriageDecision(
            task_id="test-uuid-001", action="assign", project="My Project"
        )
        assert d.project == "My Project"

    @pytest.mark.unit
    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            TriageDecision(task_id="test-uuid-001", action="invalid")

    @pytest.mark.unit
    def test_missing_task_id(self):
        with pytest.raises(ValidationError):
            TriageDecision(action="complete")

    @pytest.mark.unit
    def test_optional_notes(self):
        d = TriageDecision(task_id="test-uuid-001", action="complete", notes="Done!")
        assert d.notes == "Done!"


# ============================================================================
# 3. bulk-capture tests
# ============================================================================


class TestBulkCapture:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_execute_json = mock.Mock(return_value=True)
        self.mock_ensure_tags = mock.Mock()
        self.mock_app_state = mock.Mock()
        self.mock_app_state.update_app_state = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_batch.execute_json", self.mock_execute_json
        )
        monkeypatch.setattr(
            "things_mcp.tools_batch.ensure_tags_exist", self.mock_ensure_tags
        )
        monkeypatch.setattr("things_mcp.tools_batch.app_state", self.mock_app_state)
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_capture = _get_tool(mcp, "bulk-capture")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_captures_multiple_items(self):
        items = [
            CaptureItem(title="Task A"),
            CaptureItem(title="Task B", notes="Some notes"),
            CaptureItem(title="Task C", when="today"),
        ]
        result = await self.bulk_capture(items=items)
        assert "Captured 3 items" in result
        assert "Task A" in result
        assert "Task B" in result
        assert "Task C" in result
        self.mock_execute_json.assert_called_once()
        # Verify correct number of todo objects were built
        todo_objects = self.mock_execute_json.call_args[0][0]
        assert len(todo_objects) == 3

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_default_when_applied(self):
        items = [
            CaptureItem(title="No schedule"),
            CaptureItem(title="Has schedule", when="tomorrow"),
        ]
        result = await self.bulk_capture(items=items, default_when="today")
        assert "default schedule: today" in result
        self.mock_execute_json.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tags_collected_and_ensured(self):
        items = [
            CaptureItem(title="A", tags=["@phone"]),
            CaptureItem(title="B", tags=["@computer", "@phone"]),
        ]
        await self.bulk_capture(items=items)
        # ensure_tags_exist should be called with all unique tags
        self.mock_ensure_tags.assert_called_once()
        called_tags = set(self.mock_ensure_tags.call_args[0][0])
        assert called_tags == {"@phone", "@computer"}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_empty_items_error(self):
        with pytest.raises(ToolError, match="empty"):
            await self.bulk_capture(items=[])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execute_json_failure(self):
        self.mock_execute_json.return_value = False
        items = [CaptureItem(title="Will fail")]
        with pytest.raises(ToolError, match="Failed"):
            await self.bulk_capture(items=items)


# ============================================================================
# 4. bulk-complete tests
# ============================================================================


class TestBulkComplete:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_run_applescript = mock.Mock(return_value="ok")
        self.mock_app_state = mock.Mock()
        self.mock_app_state.update_app_state = mock.Mock(return_value=True)
        self.mock_triage_tracker = mock.Mock()
        monkeypatch.setattr(
            "things_mcp.tools_batch.run_applescript", self.mock_run_applescript
        )
        monkeypatch.setattr("things_mcp.tools_batch.app_state", self.mock_app_state)
        monkeypatch.setattr(
            "things_mcp.tools_batch.triage_tracker", self.mock_triage_tracker
        )
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_complete = _get_tool(mcp, "bulk-complete")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_completes_multiple_tasks(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
            create_mock_todo(uuid_str="test-id-002", title="Task 2"),
        ]
        result = await self.bulk_complete(task_ids=["test-id-001", "test-id-002"])
        assert "Completed 2 tasks" in result
        assert "Task 1" in result
        assert "Task 2" in result
        # Single AppleScript call with UUID loop
        self.mock_run_applescript.assert_called_once()
        script = self.mock_run_applescript.call_args[0][0]
        assert '"test-id-001"' in script
        assert '"test-id-002"' in script
        assert "completed" in script

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tracks_triage_actions(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
            create_mock_todo(uuid_str="test-id-002", title="Task 2"),
        ]
        await self.bulk_complete(task_ids=["test-id-001", "test-id-002"])
        assert self.mock_triage_tracker.record.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_applescript_failure(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
        ]
        self.mock_run_applescript.return_value = False
        with pytest.raises(ToolError, match="AppleScript failed"):
            await self.bulk_complete(task_ids=["test-id-001"])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_single_applescript_call(self):
        """Verify that even with many tasks, only one AppleScript call is made."""
        ids = [f"test-uuid-{i:03d}" for i in range(10)]
        self.things.get.side_effect = [
            create_mock_todo(uuid_str=tid, title=f"Task {i}")
            for i, tid in enumerate(ids)
        ]
        await self.bulk_complete(task_ids=ids)
        self.mock_run_applescript.assert_called_once()


# ============================================================================
# 5. bulk-cancel tests
# ============================================================================


class TestBulkCancel:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_run_applescript = mock.Mock(return_value="ok")
        self.mock_app_state = mock.Mock()
        self.mock_app_state.update_app_state = mock.Mock(return_value=True)
        self.mock_triage_tracker = mock.Mock()
        monkeypatch.setattr(
            "things_mcp.tools_batch.run_applescript", self.mock_run_applescript
        )
        monkeypatch.setattr("things_mcp.tools_batch.app_state", self.mock_app_state)
        monkeypatch.setattr(
            "things_mcp.tools_batch.triage_tracker", self.mock_triage_tracker
        )
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_cancel = _get_tool(mcp, "bulk-cancel")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancels_multiple_tasks(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
            create_mock_todo(uuid_str="test-id-002", title="Task 2"),
        ]
        result = await self.bulk_cancel(task_ids=["test-id-001", "test-id-002"])
        assert "Canceled 2 tasks" in result
        assert "Task 1" in result
        assert "Task 2" in result
        self.mock_run_applescript.assert_called_once()
        script = self.mock_run_applescript.call_args[0][0]
        assert '"test-id-001"' in script
        assert '"test-id-002"' in script
        assert "canceled" in script

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_tracks_triage_actions(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
        ]
        await self.bulk_cancel(task_ids=["test-id-001"])
        self.mock_triage_tracker.record.assert_called_once()
        call_kwargs = self.mock_triage_tracker.record.call_args[1]
        assert call_kwargs["action"] == "canceled"
        assert call_kwargs["action_details"]["bulk"] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_applescript_failure(self):
        self.things.get.side_effect = [
            create_mock_todo(uuid_str="test-id-001", title="Task 1"),
        ]
        self.mock_run_applescript.return_value = False
        with pytest.raises(ToolError, match="AppleScript failed"):
            await self.bulk_cancel(task_ids=["test-id-001"])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_single_applescript_call(self):
        ids = [f"test-uuid-{i:03d}" for i in range(5)]
        self.things.get.side_effect = [
            create_mock_todo(uuid_str=tid, title=f"Task {i}")
            for i, tid in enumerate(ids)
        ]
        await self.bulk_cancel(task_ids=ids)
        self.mock_run_applescript.assert_called_once()


# ============================================================================
# 6. bulk-modify tests
# ============================================================================


class TestBulkModify:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_execute_url = mock.Mock(return_value=True)
        self.mock_ensure_tags = mock.Mock()
        self.mock_update_todo = mock.Mock(return_value="things:///update?id=test")
        self.mock_resolve_list_id = mock.Mock(return_value="resolved-uuid")
        self.mock_app_state = mock.Mock()
        self.mock_app_state.update_app_state = mock.Mock(return_value=True)
        monkeypatch.setattr("things_mcp.tools_batch.execute_url", self.mock_execute_url)
        monkeypatch.setattr(
            "things_mcp.tools_batch.ensure_tags_exist", self.mock_ensure_tags
        )
        monkeypatch.setattr("things_mcp.tools_batch.update_todo", self.mock_update_todo)
        monkeypatch.setattr(
            "things_mcp.tools_batch.resolve_list_id", self.mock_resolve_list_id
        )
        monkeypatch.setattr("things_mcp.tools_batch.app_state", self.mock_app_state)
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_modify = _get_tool(mcp, "bulk-modify")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_modify_when(self):
        result = await self.bulk_modify(
            task_ids=["test-id-001", "test-id-002"], when="tomorrow"
        )
        assert "Modified 2 tasks" in result
        assert "scheduled to tomorrow" in result
        assert self.mock_update_todo.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_modify_add_tags(self):
        result = await self.bulk_modify(
            task_ids=["test-id-001"], add_tags=["@computer"]
        )
        assert "Modified 1 tasks" in result
        assert "tagged with @computer" in result
        self.mock_ensure_tags.assert_called_once_with(["@computer"])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_modify_project(self):
        result = await self.bulk_modify(task_ids=["test-id-001"], project="My Project")
        assert "moved to project" in result
        self.mock_resolve_list_id.assert_called_once_with("My Project", "project")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_modify_area(self):
        result = await self.bulk_modify(task_ids=["test-id-001"], area="Work")
        assert "moved to area" in result
        self.mock_resolve_list_id.assert_called_once_with("Work", "area")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_project_and_area_mutually_exclusive(self):
        with pytest.raises(ToolError, match="mutually exclusive"):
            await self.bulk_modify(
                task_ids=["test-id-001"], project="Proj", area="Area"
            )

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_modifications_error(self):
        with pytest.raises(ToolError, match="at least one"):
            await self.bulk_modify(task_ids=["test-id-001"])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_todo_called_per_task(self):
        ids = ["test-id-001", "test-id-002", "test-id-003"]
        await self.bulk_modify(task_ids=ids, when="today")
        assert self.mock_update_todo.call_count == 3
        assert self.mock_execute_url.call_count == 3


# ============================================================================
# 7. bulk-triage tests
# ============================================================================


class TestBulkTriage:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_run_applescript = mock.Mock(return_value="ok")
        self.mock_execute_url = mock.Mock(return_value=True)
        self.mock_update_todo = mock.Mock(return_value="things:///update?id=test")
        self.mock_ensure_tags = mock.Mock()
        self.mock_triage_tracker = mock.Mock()
        self.mock_app_state = mock.Mock()
        self.mock_app_state.update_app_state = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_batch.run_applescript", self.mock_run_applescript
        )
        monkeypatch.setattr("things_mcp.tools_batch.execute_url", self.mock_execute_url)
        monkeypatch.setattr("things_mcp.tools_batch.update_todo", self.mock_update_todo)
        monkeypatch.setattr(
            "things_mcp.tools_batch.ensure_tags_exist", self.mock_ensure_tags
        )
        monkeypatch.setattr(
            "things_mcp.tools_batch.triage_tracker", self.mock_triage_tracker
        )
        monkeypatch.setattr("things_mcp.tools_batch.app_state", self.mock_app_state)
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_triage = _get_tool(mcp, "bulk-triage")

    def _mock_prefetch(self, ids):
        """Set up things.get to return mock todos for prefetch."""
        self.things.get.side_effect = [
            create_mock_todo(uuid_str=tid, title=f"Task {tid}") for tid in ids
        ]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_complete_uses_applescript(self):
        self._mock_prefetch(["test-id-001", "test-id-002"])
        decisions = [
            TriageDecision(task_id="test-id-001", action="complete"),
            TriageDecision(task_id="test-id-002", action="complete"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "2/2" in result
        # Should use a single AppleScript for completions
        self.mock_run_applescript.assert_called_once()
        script = self.mock_run_applescript.call_args[0][0]
        assert "completed" in script

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancel_uses_applescript(self):
        self._mock_prefetch(["test-id-001"])
        decisions = [
            TriageDecision(task_id="test-id-001", action="cancel"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1/1" in result
        self.mock_run_applescript.assert_called_once()
        script = self.mock_run_applescript.call_args[0][0]
        assert "canceled" in script

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_defer_uses_url_scheme(self):
        self._mock_prefetch(["test-id-001"])
        decisions = [
            TriageDecision(task_id="test-id-001", action="defer", when="someday"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1/1" in result
        # Defer uses update_todo URL scheme, not AppleScript
        self.mock_update_todo.assert_called()
        self.mock_execute_url.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_schedule_uses_url_scheme(self):
        self._mock_prefetch(["test-id-001"])
        decisions = [
            TriageDecision(task_id="test-id-001", action="schedule", when="tomorrow"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1/1" in result
        self.mock_update_todo.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delegate_adds_waiting_tag(self):
        self._mock_prefetch(["test-id-001"])
        decisions = [
            TriageDecision(
                task_id="test-id-001", action="delegate", delegated_to="Bob"
            ),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1/1" in result
        self.mock_ensure_tags.assert_called_with(["waiting-for"])
        # update_todo should be called with add_tags=["waiting-for"]
        self.mock_update_todo.assert_called_once()
        call_kwargs = self.mock_update_todo.call_args[1]
        assert "waiting-for" in call_kwargs.get("add_tags", [])

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mixed_actions_grouped(self):
        """Verify complete/cancel use AppleScript and defer/schedule use URL scheme."""
        ids = ["test-id-001", "test-id-002", "test-id-003", "test-id-004"]
        self._mock_prefetch(ids)
        decisions = [
            TriageDecision(task_id="test-id-001", action="complete"),
            TriageDecision(task_id="test-id-002", action="cancel"),
            TriageDecision(task_id="test-id-003", action="defer", when="someday"),
            TriageDecision(task_id="test-id-004", action="schedule", when="tomorrow"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "4/4" in result
        # Two AppleScript calls: one for completes, one for cancels
        assert self.mock_run_applescript.call_count == 2
        # URL scheme calls for defer + schedule
        assert self.mock_update_todo.call_count >= 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_applescript_failure_counted(self):
        self._mock_prefetch(["test-id-001"])
        self.mock_run_applescript.return_value = False
        decisions = [
            TriageDecision(task_id="test-id-001", action="complete"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1 failed" in result
        assert "AppleScript failed" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_url_scheme_failure_counted(self):
        self._mock_prefetch(["test-id-001"])
        self.mock_execute_url.return_value = False
        decisions = [
            TriageDecision(task_id="test-id-001", action="defer", when="tomorrow"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "1 failed" in result or "0/1" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_action_counts_in_summary(self):
        ids = ["test-id-001", "test-id-002", "test-id-003"]
        self._mock_prefetch(ids)
        decisions = [
            TriageDecision(task_id="test-id-001", action="complete"),
            TriageDecision(task_id="test-id-002", action="complete"),
            TriageDecision(task_id="test-id-003", action="cancel"),
        ]
        result = await self.bulk_triage(decisions=decisions)
        assert "complete: 2" in result
        assert "cancel: 1" in result

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_defer_with_notes_appends(self):
        self._mock_prefetch(["test-id-001"])
        decisions = [
            TriageDecision(
                task_id="test-id-001",
                action="defer",
                when="someday",
                notes="Need more info",
            ),
        ]
        await self.bulk_triage(decisions=decisions)
        # Should be called twice: once for notes append, once for when update
        assert self.mock_update_todo.call_count == 2
        # First call should append notes
        first_call_kwargs = self.mock_update_todo.call_args_list[0][1]
        assert "Need more info" in first_call_kwargs.get("append_notes", "")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_assign_creates_project_and_cancels_task(self):
        """Assign action should create a project from the task and cancel the original."""
        task = create_mock_todo(
            uuid_str="test-id-001", title="Big idea", notes="Details here"
        )
        # First call is for prefetch_titles, then for assign lookup inside the loop
        self.things.get.side_effect = [task, task]
        mock_add_project = mock.Mock(
            return_value="things:///add-project?title=Big+idea"
        )
        # Patch add_project_with_tasks in the url_scheme module (imported lazily inside the function)
        with mock.patch(
            "things_mcp.url_scheme.add_project_with_tasks", mock_add_project
        ):
            decisions = [
                TriageDecision(
                    task_id="test-id-001", action="assign", project="Big idea"
                ),
            ]
            result = await self.bulk_triage(decisions=decisions)
        # execute_url called for project creation + task cancellation
        assert self.mock_execute_url.call_count >= 2
        assert "1/1" in result
