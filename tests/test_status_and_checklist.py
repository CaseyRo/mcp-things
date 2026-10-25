"""Status vocabulary across the read tools (CDI-1543 part 2) and native
checklists on create (CDI-1313), driven through the MCP client against a fake
Things: the URL scheme writes into a throwaway SQLite file that the real
reader then reads back.
"""

import time
import uuid
from datetime import date
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from fastmcp import Client

from tests import test_sqlite_reader_checklist as sq
from things_mcp.sqlite_reader import (
    START_ANYTIME,
    STATUS_CANCELED,
    STATUS_COMPLETED,
    TYPE_PROJECT,
    ThingsSQLiteReader,
)
from things_mcp.tool_results import unapplied

pytestmark = [pytest.mark.unit]

test_db = sq.test_db  # the minimal Things schema fixture


def _fake_add(conn, url: str) -> bool:
    """Stand in for Things handling `things:///add`: store what the URL asks for."""
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    day, _, at = q.get("when", "").partition("@")
    hh, _, mm = at.partition(":")
    task = uuid.uuid4().hex[:22]
    today = date.today()
    sq._insert_task(
        conn,
        task,
        q["title"],
        start=START_ANYTIME,
        startDate=sq._things_date(today.year, today.month, today.day)
        if day == "today"
        else None,
        reminderTime=(int(hh) << 26 | int(mm) << 20) if at else None,
        creationDate=time.time(),
    )
    for i, item in enumerate(q.get("checklist-items", "").splitlines()):
        sq._insert_checklist_item(conn, f"{task}-{i}", task, item, index=i)
    return True


@pytest.fixture
def fake_things(test_db, monkeypatch):
    conn, db_path = test_db
    reader = ThingsSQLiteReader(db_path)
    monkeypatch.setattr("things_mcp.reader._get_sqlite_reader", lambda: reader)
    monkeypatch.setattr("things_mcp.reader.READBACK_DELAYS", (0,))
    monkeypatch.setattr("things_mcp.config.get_things_auth_token", lambda: "")
    monkeypatch.setattr(
        "things_mcp.tools_gtd_core.app_state",
        mock.Mock(update_app_state=mock.Mock(return_value=True)),
    )
    monkeypatch.setattr(
        "things_mcp.tools_gtd_core.execute_url", lambda url: _fake_add(conn, url)
    )
    # Never let a things-py fallback or title lookup reach the live database.
    monkeypatch.setenv("THINGSDB", db_path)
    monkeypatch.setattr("things_mcp.formatters._resolve_title", lambda _u: None)
    from things_mcp.write_overlay import get_overlay

    get_overlay().clear()
    yield conn
    get_overlay().clear()


async def _data(client, tool, args=None):
    result = await client.call_tool(tool, args or {})
    return result.structured_content


async def test_reminder_and_checklist_round_trip(fake_things):
    """Set a reminder and a checklist through the MCP, read both back through it."""
    from things_mcp.fast_server import mcp

    async with Client(mcp) as client:
        env = await _data(
            client,
            "capture-task",
            {"title": "Pack", "when": "today@16:00", "checklist": ["Tent", "Stove"]},
        )
        assert env["data"]["thing_id"]
        assert env["meta"]["confirmed"] is True
        assert env["meta"]["unapplied"] == []

        (todo,) = (await _data(client, "get-tasks", {"view": "today"}))["data"]
    assert todo["uuid"] == env["data"]["thing_id"]
    assert todo["reminder_time"] == "16:00"
    assert [c["title"] for c in todo["checklist"]] == ["Tent", "Stove"]


def test_unapplied_flags_a_dropped_checklist():
    todo = {"tags": [], "checklist": [{"title": "Tent"}], "start_date": None}
    assert unapplied(todo, checklist=["Tent ", ""]) == []
    assert unapplied(todo, checklist=["Tent", "Stove"]) == [
        "checklist (Things shows 1 items)"
    ]


def _seed_statuses(conn):
    sq._insert_task(conn, "P-OPEN", "Open project", type=TYPE_PROJECT)
    sq._insert_task(
        conn, "P-DONE", "Done project", type=TYPE_PROJECT, status=STATUS_COMPLETED
    )
    sq._insert_task(
        conn, "P-GONE", "Dropped project", type=TYPE_PROJECT, status=STATUS_CANCELED
    )
    sq._insert_task(conn, "T-OPEN", "Invoice open", project="P-DONE")
    sq._insert_task(
        conn, "T-DONE", "Invoice paid", status=STATUS_COMPLETED, project="P-DONE"
    )
    sq._insert_task(conn, "T-GONE", "Invoice void", status=STATUS_CANCELED)


async def test_one_status_vocabulary_across_reads(fake_things):
    from things_mcp.fast_server import mcp

    _seed_statuses(fake_things)

    def uuids(env):
        return sorted(item["uuid"] for item in env["data"])

    async with Client(mcp) as client:
        tasks = lambda **a: _data(client, "get-tasks", a)  # noqa: E731
        assert uuids(await tasks()) == ["T-OPEN"]
        assert uuids(await tasks(status=["canceled"])) == ["T-GONE"]
        assert uuids(await tasks(status="completed")) == ["T-DONE"]
        # Deprecated alias: open + completed, never canceled.
        assert uuids(await tasks(include_completed=True)) == ["T-DONE", "T-OPEN"]
        # status wins over the alias.
        env = await tasks(status=["canceled"], include_completed=True)
        assert uuids(env) == ["T-GONE"] and env["meta"]["status"] == ["canceled"]

        projects = lambda **a: _data(client, "get-projects", a)  # noqa: E731
        assert uuids(await projects()) == ["P-OPEN"]
        finished = await projects(status=["completed", "canceled"])
        assert uuids(finished) == ["P-DONE", "P-GONE"]

        search = lambda **a: _data(client, "search-tasks", a)  # noqa: E731
        assert uuids(await search(query="Invoice")) == ["T-OPEN"]
        assert uuids(
            await search(query="Invoice", status=["completed", "canceled"])
        ) == [
            "T-DONE",
            "T-GONE",
        ]
        # project filter, by title or UUID, composes with query and status.
        everything = ["incomplete", "completed", "canceled"]
        by_title = await search(
            query="Invoice", project="Done project", status=everything
        )
        assert uuids(by_title) == ["T-DONE", "T-OPEN"]
        assert uuids(await search(project="P-DONE", status="completed")) == ["T-DONE"]


class TestViewPrecedence:
    """The view picks the list; status filters within it (mocked reader)."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_things, mock_utils):
        from tests.conftest import create_mock_todo
        from things_mcp.fast_server import mcp

        self.things = mock_things
        self.rows = [
            create_mock_todo(uuid_str=s, status=s) for s in ("completed", "canceled")
        ]
        self.get_tasks = mcp._local_provider._components["tool:get-tasks@"].fn
        self.get_areas = mcp._local_provider._components["tool:get-areas@"].fn

    async def test_logbook_defaults_to_both_finished_statuses(self):
        self.things.logbook.return_value = self.rows
        env = (await self.get_tasks(view="logbook")).structured_content
        assert [t["uuid"] for t in env["data"]] == ["completed", "canceled"]
        env = (
            await self.get_tasks(view="logbook", status="canceled")
        ).structured_content
        assert [t["uuid"] for t in env["data"]] == ["canceled"]

    async def test_trash_defaults_to_every_status(self):
        self.things.trash.return_value = self.rows
        env = (await self.get_tasks(view="trash")).structured_content
        assert len(env["data"]) == 2
        assert env["meta"]["status"] == ["incomplete", "completed", "canceled"]

    async def test_get_areas_status_filters_embedded_items(self):
        self.things.areas.return_value = [{"uuid": "A1", "title": "Home"}]
        await self.get_areas(include_items=True, status=["completed", "canceled"])
        calls = [c.kwargs for c in self.things.projects.call_args_list]
        assert {c["status"] for c in calls} == {"completed", "canceled"}
        assert {c["area"] for c in calls} == {"A1"}


async def test_plan_project_and_bulk_capture_send_native_checklists(monkeypatch):
    """Both JSON-API creates turn `checklist` titles into checklist-item objects."""
    import json

    from things_mcp.fast_server import mcp

    sent = []
    for mod in ("tools_gtd_organize", "tools_batch"):
        monkeypatch.setattr(
            f"things_mcp.{mod}.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
    monkeypatch.setattr("things_mcp.tools_batch.record_write", mock.Mock())
    monkeypatch.setattr("things_mcp.reader._get_sqlite_reader", lambda: None)
    monkeypatch.setattr("things_mcp.config.get_things_auth_token", lambda: "")
    monkeypatch.setattr(
        "things_mcp.tools_gtd_organize.execute_url",
        lambda url: (
            sent.append(json.loads(parse_qs(urlparse(url).query)["data"][0])) or True
        ),
    )
    monkeypatch.setattr(
        "things_mcp.tools_batch.execute_json", lambda items: sent.append(items) or True
    )
    item = [
        {"type": "checklist-item", "attributes": {"title": "Tent"}},
        {"type": "checklist-item", "attributes": {"title": "Stove"}},
    ]
    async with Client(mcp) as client:
        await client.call_tool(
            "plan-project",
            {
                "title": "Trip",
                "tasks": [
                    {"title": "Pack", "checklist": ["Tent", "Stove"]},
                    {"title": "Drive", "checklist": "Tent\nStove"},  # untyped dict
                ],
            },
        )
        await client.call_tool(
            "bulk-capture",
            {"items": [{"title": "Pack", "checklist": ["Tent", "Stove"]}]},
        )

    (project,), (todo,) = sent
    tasks = project["attributes"]["items"]
    assert [t["attributes"]["checklist-items"] for t in tasks] == [item, item]
    assert todo["attributes"]["checklist-items"] == item
