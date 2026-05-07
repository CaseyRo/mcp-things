"""Unit tests for GTD Reflect tools (daily-review, weekly-review)."""

import pytest

from tests.conftest import create_mock_todo, create_mock_project, tool_text


class TestWeeklyReview:
    """Test weekly-review tool."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.weekly_review = mcp._local_provider._components["tool:weekly-review@"].fn

    @pytest.mark.asyncio
    async def test_empty_system(self):
        self.things.inbox.return_value = []
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        self.things.someday.return_value = []
        self.things.last.return_value = []
        result = await self.weekly_review()
        text = tool_text(result)
        assert "Weekly Review" in text
        assert "Inbox: Clear" in text
        envelope = result.structured_content
        assert envelope["data"]["period"] == "weekly"

    @pytest.mark.asyncio
    async def test_inbox_items_shown(self):
        self.things.inbox.return_value = [
            create_mock_todo(title="Item 1"),
            create_mock_todo(title="Item 2"),
        ]
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        self.things.someday.return_value = []
        self.things.last.return_value = []
        result = await self.weekly_review()
        text = tool_text(result)
        assert "2 items" in text
        assert "Process to zero" in text
        assert result.structured_content["data"]["inbox_count"] == 2

    @pytest.mark.asyncio
    async def test_stalled_projects_detected(self):
        project = create_mock_project(
            uuid_str="p1", title="Stalled Project", status="incomplete"
        )
        self.things.inbox.return_value = []
        self.things.projects.return_value = [project]
        # No available tasks for the project
        self.things.todos.return_value = []
        self.things.someday.return_value = []
        self.things.last.return_value = []
        result = await self.weekly_review()
        text = tool_text(result)
        assert "Stalled" in text
        assert "Stalled Project" in text

    @pytest.mark.asyncio
    async def test_waiting_for_items(self):
        self.things.inbox.return_value = []
        self.things.projects.return_value = []
        waiting = [create_mock_todo(title="Waiting on Bob", tags=["waiting-for"])]
        # First call: all incomplete todos (stalled project group-by), second: waiting-for items
        self.things.todos.side_effect = [[], waiting]
        self.things.someday.return_value = []
        self.things.last.return_value = []
        result = await self.weekly_review()
        assert "Waiting For" in tool_text(result)

    @pytest.mark.asyncio
    async def test_completed_this_week(self):
        self.things.inbox.return_value = []
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        self.things.someday.return_value = []
        self.things.last.return_value = [
            create_mock_todo(title="Done task 1"),
            create_mock_todo(title="Done task 2"),
        ]
        result = await self.weekly_review()
        text = tool_text(result)
        assert "Completed This Week: 2" in text
        assert "Celebrate" in text
        assert len(result.structured_content["data"]["completed"]) == 2

    @pytest.mark.asyncio
    async def test_someday_items(self):
        self.things.inbox.return_value = []
        self.things.projects.return_value = []
        self.things.todos.return_value = []
        self.things.someday.return_value = [
            create_mock_todo(title="Learn guitar"),
        ]
        self.things.last.return_value = []
        result = await self.weekly_review()
        text = tool_text(result)
        assert "Someday/Maybe" in text
        assert "Learn guitar" in text
