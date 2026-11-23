"""COS-277: single checklist items, the other update gaps, bulk-complete merge."""

import json
import urllib.parse
from unittest import mock

import pytest
from fastmcp.exceptions import ToolError

from tests.conftest import create_mock_todo, tool_text
from things_mcp.tools_gtd_organize import ChecklistRename, edit_checklist
from things_mcp.url_scheme import update_checklist_json, update_todo

ITEMS = [
    {"title": "Mon 23.11: re-check", "status": "incomplete", "uuid": "c1"},
    {"title": "Send draft", "status": "completed", "uuid": "c2"},
    {"title": "Old idea", "status": "canceled", "uuid": "c3"},
]


def _attrs(items):
    return [i["attributes"] for i in items]


def _params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


@pytest.fixture(autouse=True)
def _no_token(monkeypatch):
    monkeypatch.setattr("things_mcp.config.get_things_auth_token", lambda: "tok")


class TestEditChecklist:
    def test_check_by_fragment_keeps_the_rest(self):
        out = _attrs(edit_checklist(ITEMS, check=["re-check"]))
        assert out == [
            {"title": "Mon 23.11: re-check", "completed": True},
            {"title": "Send draft", "completed": True},
            {"title": "Old idea", "canceled": True},
        ]

    def test_uncheck_by_position(self):
        out = _attrs(edit_checklist(ITEMS, uncheck=["2"]))
        assert out[1] == {"title": "Send draft"}

    def test_rename_and_remove(self):
        out = _attrs(
            edit_checklist(
                ITEMS,
                rename=[ChecklistRename(item="send draft", title="Send final")],
                remove=["3"],
            )
        )
        assert [a["title"] for a in out] == ["Mon 23.11: re-check", "Send final"]

    def test_ambiguous_fragment_asks_for_position(self):
        with pytest.raises(ToolError, match="pass the position"):
            edit_checklist(ITEMS, check=["e"])

    def test_no_match_lists_items(self):
        with pytest.raises(ToolError, match=r"1\. Mon 23\.11"):
            edit_checklist(ITEMS, check=["nothing like it"])

    def test_position_out_of_range(self):
        with pytest.raises(ToolError, match="no item 9"):
            edit_checklist(ITEMS, check=["9"])

    def test_empty_checklist(self):
        with pytest.raises(ToolError, match="no checklist"):
            edit_checklist([], check=["1"])


class TestUrls:
    def test_checklist_json_is_an_update(self):
        url = update_checklist_json("T1", [{"type": "checklist-item"}])
        p = _params(url)
        assert url.startswith("things:///json?")
        assert p["auth-token"] == "tok"
        assert json.loads(p["data"]) == [
            {
                "type": "to-do",
                "operation": "update",
                "id": "T1",
                "attributes": {"checklist-items": [{"type": "checklist-item"}]},
            }
        ]

    def test_update_gaps(self):
        p = _params(
            update_todo(
                id="T1",
                prepend_notes="top",
                heading="Later",
                heading_id="H1",
                completed=False,
                duplicate=True,
            )
        )
        assert p["prepend-notes"] == "top"
        assert p["heading"] == "Later"
        assert p["heading-id"] == "H1"
        assert p["completed"] == "false"
        assert p["duplicate"] == "true"

    def test_markdown_notes_pass_through(self):
        md = "# Plan\n\n- [ ] one\n- **bold** & _it_ + `code`\n> quote"
        url = update_todo(id="T1", notes=md)
        assert "%0A" in url
        assert _params(url)["notes"] == md


class TestModifyTaskChecklist:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.things.get.return_value = create_mock_todo(uuid_str="T1")
        self.urls = []
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.execute_url",
            lambda url: self.urls.append(url) or True,
        )
        monkeypatch.setattr(
            "things_mcp.tools_gtd_organize.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        after = [dict(i) for i in ITEMS]
        after[0]["status"] = "completed"
        self.reads = iter([ITEMS, after])
        monkeypatch.setattr(
            "things_mcp.reader.checklist_items", lambda _id: next(self.reads)
        )
        from things_mcp.fast_server import mcp

        self.modify_task = mcp._local_provider._components["tool:modify-task@"].fn

    @pytest.mark.asyncio
    async def test_tick_one_item_reads_back(self):
        result = await self.modify_task(task_id="T1", check_items=["re-check"])
        assert len(self.urls) == 1  # checklist-only: no update URL
        assert self.urls[0].startswith("things:///json?")
        assert result.structured_content["meta"]["checklist_confirmed"] is True
        assert "read back" in tool_text(result)

    @pytest.mark.asyncio
    async def test_with_other_fields_sends_both(self):
        await self.modify_task(task_id="T1", title="New", check_items=["1"])
        assert self.urls[0].startswith("things:///update?")
        assert self.urls[1].startswith("things:///json?")

    @pytest.mark.asyncio
    async def test_bad_selector_writes_nothing(self):
        with pytest.raises(ToolError):
            await self.modify_task(task_id="T1", title="New", check_items=["zzz"])
        assert self.urls == []

    @pytest.mark.asyncio
    async def test_conflicts(self):
        with pytest.raises(ToolError, match="not both"):
            await self.modify_task(task_id="T1", checklist=["a"], check_items=["1"])
        with pytest.raises(ToolError, match="duplicate"):
            await self.modify_task(task_id="T1", duplicate=True, remove_items=["1"])

    @pytest.mark.asyncio
    async def test_reopen(self):
        result = await self.modify_task(task_id="T1", completed=False)
        assert _params(self.urls[0])["completed"] == "false"
        assert "reopened" in tool_text(result)


class TestBulkCompleteMerge:
    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils, monkeypatch):
        self.things = mock_things
        self.urls = []
        monkeypatch.setattr(
            "things_mcp.tools_batch.execute_url",
            lambda url: self.urls.append(url) or True,
        )
        self.script = mock.Mock(return_value="ok")
        monkeypatch.setattr("things_mcp.tools_batch.run_applescript", self.script)
        monkeypatch.setattr(
            "things_mcp.tools_batch.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        monkeypatch.setattr("things_mcp.tools_batch.triage_tracker", mock.Mock())
        monkeypatch.setattr("things_mcp.tools_batch.things", self.things)
        from things_mcp.fast_server import mcp

        self.bulk_complete = mcp._local_provider._components["tool:bulk-complete@"].fn

    @pytest.mark.asyncio
    async def test_by_title_with_notes(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.reader.todos",
            lambda **_: [create_mock_todo(uuid_str="abc123", title="Buy milk")],
        )
        self.things.get.return_value = create_mock_todo(uuid_str="abc123")
        result = await self.bulk_complete(task_title="milk", completion_notes="done")
        assert result.structured_content["data"]["succeeded_ids"] == ["abc123"]
        assert "abc123" in self.script.call_args[0][0]
        assert _params(self.urls[0])["append-notes"] == "\n[Completed] done"

    @pytest.mark.asyncio
    async def test_needs_ids_or_title(self):
        with pytest.raises(ToolError, match="task_ids or task_title"):
            await self.bulk_complete()
