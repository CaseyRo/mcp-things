"""Tool-level tests for CDI-1255: read-after-write staleness + Inbox-as-area.

Covers:
- search-tasks / get-tasks rejecting a built-in list name passed as `area`
- staleness-aware "not found" signalling on empty reads and fuzzy lookups
- reader-level overlay merge feeding freshly captured items into reads
"""

import pytest

from tests.conftest import create_mock_todo, tool_text

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Inbox-as-area fix (secondary CDI-1255 observation)
# ---------------------------------------------------------------------------


class TestInboxIsNotAnArea:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.search_tasks = mcp._local_provider._components["tool:search-tasks@"].fn
        self.get_tasks = mcp._local_provider._components["tool:get-tasks@"].fn

    @pytest.mark.asyncio
    async def test_search_tasks_rejects_area_inbox(self):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="built-in Things list"):
            await self.search_tasks(status="incomplete", area="Inbox")

    @pytest.mark.asyncio
    async def test_search_tasks_inbox_error_points_to_view(self):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="get-tasks\\(view='inbox'\\)"):
            await self.search_tasks(area="inbox")

    @pytest.mark.asyncio
    async def test_search_tasks_rejects_other_list_names(self):
        from fastmcp.exceptions import ToolError

        for list_name in ("Today", "Anytime", "Someday", "Upcoming", "Logbook"):
            with pytest.raises(ToolError, match="built-in Things list"):
                await self.search_tasks(area=list_name)

    @pytest.mark.asyncio
    async def test_real_area_name_still_works(self):
        # A genuine area name is passed straight through to the reader filter.
        self.things.todos.return_value = [create_mock_todo(title="Area task")]
        result = await self.search_tasks(area="Work")
        assert "Area task" in tool_text(result)

    @pytest.mark.asyncio
    async def test_get_tasks_rejects_area_inbox(self):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="built-in Things list"):
            await self.get_tasks(area="Inbox")


# ---------------------------------------------------------------------------
# Staleness-aware "not found" signalling
# ---------------------------------------------------------------------------


class TestStalenessSignalling:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        self.things = mock_things
        from things_mcp.fast_server import mcp

        self.search_tasks = mcp._local_provider._components["tool:search-tasks@"].fn

    @pytest.mark.asyncio
    async def test_empty_result_not_stale_is_authoritative(self):
        self.things.search.return_value = []
        self.things.index_stale.return_value = False
        result = await self.search_tasks(query="ghost")
        text = tool_text(result)
        assert "No tasks found matching your criteria." in text
        assert "stale" not in text.lower()
        # structured meta says not stale
        assert result.structured_content["meta"]["index_stale"] is False

    @pytest.mark.asyncio
    async def test_empty_result_stale_signals_retry(self):
        self.things.search.return_value = []
        self.things.index_stale.return_value = True
        result = await self.search_tasks(query="just-captured")
        text = tool_text(result)
        assert "read index" in text.lower()
        assert result.structured_content["meta"]["index_stale"] is True


# ---------------------------------------------------------------------------
# Reader overlay merge — read-your-writes
# ---------------------------------------------------------------------------


class TestReaderOverlayMerge:
    @pytest.fixture(autouse=True)
    def _clear_overlay(self):
        from things_mcp.write_overlay import get_overlay

        get_overlay().clear()
        yield
        get_overlay().clear()

    def test_search_merges_overlay_when_sqlite_unavailable(self, monkeypatch):
        """A captured item is visible to reader.search before SQLite catches up."""
        import things_mcp.reader as reader
        from things_mcp.write_overlay import get_overlay

        # Force the things-py fallback path to return nothing (SQLite "stale").
        monkeypatch.setattr(reader, "_get_sqlite_reader", lambda: None)
        import things

        monkeypatch.setattr(things, "search", lambda q: [], raising=False)

        get_overlay().record("Freshly captured task")
        rows = reader.search("Freshly")
        titles = [r["title"] for r in rows]
        assert "Freshly captured task" in titles

    def test_todos_merges_overlay_for_broad_incomplete_query(self, monkeypatch):
        import things_mcp.reader as reader
        from things_mcp.write_overlay import get_overlay

        monkeypatch.setattr(reader, "_get_sqlite_reader", lambda: None)
        import things

        monkeypatch.setattr(things, "todos", lambda **kw: [], raising=False)

        get_overlay().record("Brand new todo")
        rows = reader.todos(status="incomplete")
        assert any(r["title"] == "Brand new todo" for r in rows)

    def test_todos_skips_overlay_for_narrow_filter(self, monkeypatch):
        """A freshly captured item has no project/area yet, so a project-filtered
        query must NOT surface it (avoids false positives)."""
        import things_mcp.reader as reader
        from things_mcp.write_overlay import get_overlay

        monkeypatch.setattr(reader, "_get_sqlite_reader", lambda: None)
        import things

        monkeypatch.setattr(things, "todos", lambda **kw: [], raising=False)

        get_overlay().record("Inbox item")
        rows = reader.todos(status="incomplete", project="some-project-uuid")
        assert rows == []

    def test_persisted_item_suppresses_overlay_duplicate(self, monkeypatch):
        import things_mcp.reader as reader
        from things_mcp.write_overlay import get_overlay

        monkeypatch.setattr(reader, "_get_sqlite_reader", lambda: None)
        import things

        # SQLite has now caught up — the real row exists.
        monkeypatch.setattr(
            things,
            "search",
            lambda q: [{"uuid": "real-1", "title": "Now persisted"}],
            raising=False,
        )

        get_overlay().record("Now persisted")
        rows = reader.search("persisted")
        assert len(rows) == 1
        assert rows[0]["uuid"] == "real-1"
