"""Unit tests for project/area CRUD tools, security hardening, and GTD integration.

Tests cover: get-project, get-area, modify-project, modify-area, delete-area,
merge-areas, enhanced plan-project/create-area, security (escape, validation),
and GTD layer updates (convert-to-project, process-inbox, weekly/daily review).
"""

import pytest
from unittest import mock
from fastmcp.exceptions import ToolError

from tests.conftest import (
    create_mock_todo,
    create_mock_project,
    create_mock_area,
)


# ============================================================================
# Helpers
# ============================================================================


def _get_tool(mcp, name):
    """Get a tool function from the MCP server."""
    return mcp._local_provider._components[f"tool:{name}@"].fn


# ============================================================================
# 9.1: get-project tests
# ============================================================================


class TestGetProject:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.get_project = _get_tool(mcp, "get-project")

    @pytest.mark.asyncio
    async def test_get_by_name(self):
        proj = create_mock_project(
            uuid_str="proj-1", title="My Project", notes="Some notes"
        )
        self.things.get.return_value = None
        self.things.projects.return_value = [proj]
        self.things.todos.return_value = []
        result = await self.get_project(name_or_uuid="My Project")
        assert "My Project" in result
        assert "proj-1" in result

    @pytest.mark.asyncio
    async def test_get_by_uuid(self):
        proj = create_mock_project(uuid_str="proj-uuid-123", title="Found")
        self.things.get.return_value = proj
        self.things.todos.return_value = []
        result = await self.get_project(name_or_uuid="proj-uuid-123")
        assert "Found" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        self.things.get.return_value = None
        self.things.projects.return_value = []
        with pytest.raises(ToolError, match="not found"):
            await self.get_project(name_or_uuid="nonexistent")

    @pytest.mark.asyncio
    async def test_ambiguous_name(self):
        p1 = create_mock_project(uuid_str="p1", title="Dup")
        p2 = create_mock_project(uuid_str="p2", title="Dup")
        self.things.get.return_value = None
        self.things.projects.return_value = [p1, p2]
        with pytest.raises(ToolError, match="Multiple"):
            await self.get_project(name_or_uuid="Dup")


# ============================================================================
# 9.2: modify-project tests
# ============================================================================


class TestModifyProject:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_execute = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", self.mock_execute
        )
        from things_mcp.fast_server import mcp

        self.modify_project = _get_tool(mcp, "modify-project")

    @pytest.mark.asyncio
    async def test_rename(self):
        self.things.get.return_value = create_mock_project(uuid_str="p1")
        result = await self.modify_project(name_or_uuid="p1", title="New Name")
        assert "title updated" in result
        self.mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_area_reassignment(self):
        self.things.get.side_effect = [
            create_mock_project(uuid_str="p1"),  # project lookup
            None,  # area name lookup (not UUID)
        ]
        self.things.areas.return_value = [
            create_mock_area(uuid_str="area-1", title="Work")
        ]
        result = await self.modify_project(name_or_uuid="p1", area="Work")
        assert "moved to area" in result

    @pytest.mark.asyncio
    async def test_complete_with_incomplete_tasks_warning(self):
        self.things.get.return_value = create_mock_project(uuid_str="p1")
        self.things.todos.return_value = [
            create_mock_todo(title="Task 1"),
            create_mock_todo(title="Task 2"),
        ]
        result = await self.modify_project(name_or_uuid="p1", completed=True)
        assert "2 incomplete tasks" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        self.things.get.return_value = None
        self.things.projects.return_value = []
        with pytest.raises(ToolError, match="not found"):
            await self.modify_project(name_or_uuid="nonexistent", title="X")


# ============================================================================
# 9.3: get-area tests
# ============================================================================


class TestGetArea:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.get_area = _get_tool(mcp, "get-area")

    @pytest.mark.asyncio
    async def test_get_by_name(self):
        area = create_mock_area(uuid_str="a1", title="Work")
        self.things.get.return_value = None
        self.things.areas.return_value = [area]
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        result = await self.get_area(name_or_uuid="Work")
        assert "Work" in result
        assert "a1" in result

    @pytest.mark.asyncio
    async def test_get_by_uuid(self):
        area = create_mock_area(uuid_str="area-uuid", title="Health")
        self.things.get.return_value = area
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        result = await self.get_area(name_or_uuid="area-uuid")
        assert "Health" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        self.things.get.return_value = None
        self.things.areas.return_value = []
        with pytest.raises(ToolError, match="not found"):
            await self.get_area(name_or_uuid="nonexistent")

    @pytest.mark.asyncio
    async def test_ambiguous(self):
        a1 = create_mock_area(uuid_str="a1", title="Work")
        a2 = create_mock_area(uuid_str="a2", title="Work")
        self.things.get.return_value = None
        self.things.areas.return_value = [a1, a2]
        with pytest.raises(ToolError, match="Multiple"):
            await self.get_area(name_or_uuid="Work")

    @pytest.mark.asyncio
    async def test_include_items(self):
        area = create_mock_area(uuid_str="a1", title="Work")
        self.things.get.return_value = area
        proj = create_mock_project(uuid_str="p1", title="Proj", area="a1")
        self.things.projects.return_value = [proj]
        self.things.todos.return_value = [create_mock_todo(title="Loose", area="a1")]
        result = await self.get_area(name_or_uuid="a1", include_items=True)
        assert "Proj" in result
        assert "Loose" in result


# ============================================================================
# 9.4: modify-area tests
# ============================================================================


class TestModifyArea:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_applescript = mock.Mock(return_value="ok")
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.run_applescript", self.mock_applescript
        )
        from things_mcp.fast_server import mcp

        self.modify_area = _get_tool(mcp, "modify-area")

    @pytest.mark.asyncio
    async def test_rename(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1", title="Old")
        self.things.areas.return_value = [create_mock_area(uuid_str="a1", title="Old")]
        result = await self.modify_area(name_or_uuid="a1", new_name="New")
        assert "renamed" in result
        # Verify UUID-based lookup in AppleScript
        call_args = self.mock_applescript.call_args[0][0]
        assert 'whose id is "a1"' in call_args

    @pytest.mark.asyncio
    async def test_duplicate_name_guard(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1")
        self.things.areas.return_value = [
            create_mock_area(uuid_str="a1", title="Old"),
            create_mock_area(uuid_str="a2", title="Taken"),
        ]
        with pytest.raises(ToolError, match="already taken"):
            await self.modify_area(name_or_uuid="a1", new_name="Taken")

    @pytest.mark.asyncio
    async def test_empty_name_rejected(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1")
        with pytest.raises(ToolError, match="empty"):
            await self.modify_area(name_or_uuid="a1", new_name="   ")

    @pytest.mark.asyncio
    async def test_not_found(self):
        self.things.get.return_value = None
        self.things.areas.return_value = []
        with pytest.raises(ToolError, match="not found"):
            await self.modify_area(name_or_uuid="nope", new_name="X")


# ============================================================================
# 9.5: delete-area tests
# ============================================================================


class TestDeleteArea:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_applescript = mock.Mock(return_value="ok")
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.run_applescript", self.mock_applescript
        )
        from things_mcp.fast_server import mcp

        self.delete_area = _get_tool(mcp, "delete-area")

    @pytest.mark.asyncio
    async def test_delete_empty_area(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1")
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        result = await self.delete_area(name_or_uuid="a1")
        assert "Deleted" in result

    @pytest.mark.asyncio
    async def test_delete_with_projects_only(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1")
        self.things.projects.return_value = [
            create_mock_project(title="Proj", area="a1")
        ]
        self.things.todos.return_value = []
        result = await self.delete_area(name_or_uuid="a1")
        assert "unassigned" in result

    @pytest.mark.asyncio
    async def test_blocked_by_loose_todos(self):
        self.things.get.return_value = create_mock_area(uuid_str="a1")
        self.things.projects.return_value = []
        self.things.todos.return_value = [
            create_mock_todo(title="Loose task", area="a1")
        ]
        with pytest.raises(ToolError, match="merge-areas"):
            await self.delete_area(name_or_uuid="a1")


# ============================================================================
# 9.6: merge-areas tests
# ============================================================================


class TestMergeAreas:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_applescript = mock.Mock(return_value="ok")
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.run_applescript", self.mock_applescript
        )
        from things_mcp.fast_server import mcp

        self.merge_areas = _get_tool(mcp, "merge-areas")

    @pytest.mark.asyncio
    async def test_merge_mixed_contents(self):
        self.things.get.side_effect = [
            create_mock_area(uuid_str="src"),
            create_mock_area(uuid_str="tgt"),
        ]
        # First call: scan; second call: re-read before delete
        todo = create_mock_todo(uuid_str="t1", title="Todo", area="src")
        proj = create_mock_project(uuid_str="p1", title="Proj", area="src")
        self.things.projects.side_effect = [
            [proj],  # initial scan
            [],  # re-read before delete
        ]
        self.things.todos.side_effect = [
            [todo],  # initial scan
            [],  # re-read before delete
        ]
        result = await self.merge_areas(source="src", target="tgt")
        assert "1 to-do" in result
        assert "1 project" in result
        assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_self_merge_guard_uuid(self):
        # Same UUID, different input formats
        self.things.get.side_effect = [
            create_mock_area(uuid_str="same-uuid"),
            None,  # second lookup by name
        ]
        self.things.areas.return_value = [
            create_mock_area(uuid_str="same-uuid", title="Work")
        ]
        with pytest.raises(ToolError, match="same"):
            await self.merge_areas(source="same-uuid", target="Work")

    @pytest.mark.asyncio
    async def test_empty_source(self):
        self.things.get.side_effect = [
            create_mock_area(uuid_str="src"),
            create_mock_area(uuid_str="tgt"),
        ]
        self.things.projects.side_effect = [[], []]
        self.things.todos.side_effect = [[], []]
        result = await self.merge_areas(source="src", target="tgt")
        assert "0 to-do" in result


# ============================================================================
# 9.7: Enhanced plan-project and create-area tests
# ============================================================================


class TestEnhancedPlanProject:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.mock_execute = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", self.mock_execute
        )
        from things_mcp.fast_server import mcp

        self.plan_project = _get_tool(mcp, "plan-project")

    @pytest.mark.asyncio
    async def test_with_notes(self):
        result = await self.plan_project(
            title="Test", tasks=[{"title": "Step 1"}], notes="My notes"
        )
        assert "Created project" in result

    @pytest.mark.asyncio
    async def test_name_validation(self):
        with pytest.raises(ToolError, match="empty"):
            await self.plan_project(title="  ", tasks=[{"title": "Step"}])


class TestEnhancedCreateArea:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_applescript = mock.Mock(return_value="ok")
        self.mock_execute = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.run_applescript", self.mock_applescript
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", self.mock_execute
        )
        from things_mcp.fast_server import mcp

        self.create_area = _get_tool(mcp, "create-area")

    @pytest.mark.asyncio
    async def test_with_projects(self):
        self.things.areas.return_value = []
        result = await self.create_area(name="New Area", projects=["Proj A", "Proj B"])
        assert "2 project" in result
        assert "stalled" in result

    @pytest.mark.asyncio
    async def test_without_projects_no_regression(self):
        self.things.areas.return_value = []
        result = await self.create_area(name="Simple Area")
        assert "Created area" in result
        assert "stalled" not in result


# ============================================================================
# 9.8: GTD integration tests
# ============================================================================


class TestGTDIntegration:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.mock_execute = mock.Mock(return_value=True)
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url", self.mock_execute
        )
        monkeypatch.setattr("things_mcp.tools_gtd_core.execute_url", self.mock_execute)
        from things_mcp.fast_server import mcp

        self.mcp = mcp

    @pytest.mark.asyncio
    async def test_convert_to_project_guidance(self):
        """convert-to-project should mention modify-project in success message."""
        convert = _get_tool(self.mcp, "convert-to-project")
        task = create_mock_todo(uuid_str="t1", title="Multi-step thing", status="open")
        task["type"] = "to-do"
        task["checklist"] = []
        self.things.get.return_value = task
        result = await convert(task_id="t1")
        assert "modify-project" in result

    @pytest.mark.asyncio
    async def test_convert_no_area_guidance(self):
        """convert-to-project for inbox task should note area-less state."""
        convert = _get_tool(self.mcp, "convert-to-project")
        task = create_mock_todo(uuid_str="t1", title="Inbox thing")
        task["type"] = "to-do"
        task["checklist"] = []
        task["area_title"] = None
        self.things.get.return_value = task
        result = await convert(task_id="t1")
        assert "no area" in result.lower()

    @pytest.mark.asyncio
    async def test_process_inbox_organize_guidance(self):
        """process-inbox should include organize tip about existing projects."""
        process = _get_tool(self.mcp, "process-inbox")
        self.things.inbox.return_value = [create_mock_todo(title="Some task")]
        result = await process()
        assert "schedule-task" in result
        assert "project=" in result

    @pytest.mark.asyncio
    async def test_weekly_review_unassigned_projects(self):
        """weekly-review should surface projects with no area."""
        review = _get_tool(self.mcp, "weekly-review")
        self.things.inbox.return_value = []
        self.things.projects.return_value = [
            create_mock_project(title="Orphan", status="incomplete", area=None),
        ]
        self.things.todos.return_value = []
        self.things.someday.return_value = []
        result = await review()
        assert "Unassigned" in result
        assert "modify-project" in result

    @pytest.mark.asyncio
    async def test_daily_review_overdue_projects(self):
        """daily-review should show overdue projects."""
        review = _get_tool(self.mcp, "daily-review")
        self.things.today.return_value = []
        self.things.inbox.return_value = []
        self.things.todos.return_value = []
        self.things.projects.return_value = [
            create_mock_project(
                title="Late Project", status="incomplete", deadline="2020-01-01"
            ),
        ]
        result = await review()
        assert "Overdue Projects" in result
        assert "Late Project" in result


# ============================================================================
# 9.9: Security tests
# ============================================================================


class TestSecurityHardening:
    def test_escape_strips_control_chars(self):
        from things_mcp.applescript_bridge import escape_applescript_string

        result = escape_applescript_string("hello\x00world\nfoo\tbar")
        assert "\x00" not in result
        assert "\n" not in result
        assert "\t" not in result
        assert "helloworld" in result

    def test_escape_preserves_quotes(self):
        from things_mcp.applescript_bridge import escape_applescript_string

        result = escape_applescript_string('say "hello"')
        assert result == 'say ""hello""'

    def test_validate_name_rejects_empty(self):
        from things_mcp.input_validation import validate_name

        with pytest.raises(ToolError, match="empty"):
            validate_name("")
        with pytest.raises(ToolError, match="empty"):
            validate_name("   ")

    def test_validate_name_rejects_long(self):
        from things_mcp.input_validation import validate_name

        with pytest.raises(ToolError, match="maximum length"):
            validate_name("x" * 300)

    def test_validate_name_accepts_normal(self):
        from things_mcp.input_validation import validate_name

        validate_name("Normal Area Name")  # should not raise

    def test_validate_notes_length(self):
        from things_mcp.input_validation import validate_notes_length

        with pytest.raises(ToolError, match="maximum length"):
            validate_notes_length("x" * 11000)

    def test_sensitive_fields_includes_name(self):
        from things_mcp.logging_config import SENSITIVE_FIELDS

        assert "name" in SENSITIVE_FIELDS


# ============================================================================
# 9.11: URL scheme area_id test
# ============================================================================


class TestUrlSchemeAreaId:
    def test_update_project_area_id(self):
        from things_mcp.url_scheme import update_project

        url = update_project(id="proj-123", area_id="area-456")
        assert "area-id" in url
        assert "area-456" in url
        assert "update-project" in url

    def test_update_project_no_area_id(self):
        from things_mcp.url_scheme import update_project

        url = update_project(id="proj-123", title="New Title")
        assert "area-id" not in url
