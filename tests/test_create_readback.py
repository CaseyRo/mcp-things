"""Create tools read the new to-do back for its real UUID (CDI-1588)."""

import time
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from fastmcp import Client

from things_mcp.tool_results import unapplied

pytestmark = [pytest.mark.unit]

ROW = {
    "uuid": "REAL-UUID-1",
    "type": "to-do",
    "title": "Pay rent",
    "status": "incomplete",
    "start": "Anytime",
    "start_date": None,
}


@pytest.fixture
def things_db(monkeypatch):
    """Mock the write path in every create module plus the SQLite reader."""
    for mod in ("tools_gtd_core", "tools_gtd_organize", "tools_batch"):
        target = f"things_mcp.{mod}"
        monkeypatch.setattr(
            f"{target}.app_state",
            mock.Mock(update_app_state=mock.Mock(return_value=True)),
        )
        monkeypatch.setattr(f"{target}.ensure_tags_exist", mock.Mock())
        monkeypatch.setattr(f"{target}.record_write", mock.Mock())
    monkeypatch.setattr("things_mcp.tools_gtd_core.execute_url", lambda _u: True)
    monkeypatch.setattr("things_mcp.tools_gtd_organize.execute_url", lambda _u: True)
    monkeypatch.setattr("things_mcp.tools_batch.execute_json", lambda _i: True)
    monkeypatch.setattr("things_mcp.reader.READBACK_DELAYS", (0, 0, 0))
    db = SimpleNamespace(is_available=True, find_created=mock.Mock(return_value=None))
    monkeypatch.setattr("things_mcp.reader._get_sqlite_reader", lambda: db)
    return db


async def test_found_after_lag_sets_thing_id(things_db):
    from things_mcp.fast_server import mcp

    # Things commits a beat late: the first poll misses, the second finds it.
    things_db.find_created.side_effect = [None, ROW]
    async with Client(mcp) as client:
        result = await client.call_tool("capture-task", {"title": "Pay rent"})

    env = result.structured_content
    assert env["data"]["thing_id"] == "REAL-UUID-1"
    assert env["meta"]["confirmed"] is True
    assert env["meta"]["todo"]["uuid"] == "REAL-UUID-1"
    assert "Confirmed in Things, filed in Anytime" in env["summary"]
    title, since = things_db.find_created.call_args.args
    assert title == "Pay rent" and time.time() - 10 < since <= time.time()


async def test_not_found_in_window_stays_null(things_db):
    from things_mcp.fast_server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool(
            "schedule-task", {"title": "Pay rent", "when": "today"}
        )

    env = result.structured_content
    assert env["data"]["thing_id"] is None
    assert env["meta"]["confirmed"] is False
    assert "not yet confirmed" in env["summary"]
    assert "not yet confirmed" in result.content[0].text
    assert things_db.find_created.call_count == 3  # bounded poll


async def test_project_not_applied_is_visible(things_db, monkeypatch):
    from things_mcp.fast_server import mcp

    monkeypatch.setattr(
        "things_mcp.tools_gtd_organize.resolve_list_id", lambda *_a: "PROJ-1"
    )
    things_db.find_created.return_value = ROW  # filed in Anytime, no project
    async with Client(mcp) as client:
        result = await client.call_tool(
            "schedule-task",
            {"title": "Pay rent", "when": "anytime", "project": "Finances"},
        )
        tools = {t.name: t for t in await client.list_tools()}

    env = result.structured_content
    assert env["data"]["thing_id"] == "REAL-UUID-1"
    assert "NOT applied: project (filed in Anytime)" in env["summary"]
    assert env["meta"]["unapplied"] == ["project (filed in Anytime)"]
    # The portal caches output schemas: WriteResult must keep its exact fields.
    data_schema = tools["schedule-task"].output_schema["properties"]["data"]
    assert set(data_schema["properties"]) == {"acknowledged", "thing_id", "summary"}


async def test_bulk_capture_reports_thing_ids_in_item_order(things_db):
    from things_mcp.fast_server import mcp

    things_db.find_created.side_effect = lambda title, _s: (
        ROW if title == "Pay rent" else None
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "bulk-capture", {"items": [{"title": "Pay rent"}, {"title": "Call mum"}]}
        )

    env = result.structured_content
    assert env["meta"]["thing_ids"] == ["REAL-UUID-1", None]
    assert env["data"]["succeeded_ids"] == ["Pay rent", "Call mum"]
    assert "1 not yet confirmed" in env["summary"]


def test_unapplied_compares_only_exact_fields():
    today = date.today()
    todo = {
        "project": None,
        "list": "Today",
        "tags": ["@Phone"],
        "start": "Anytime",
        "start_date": today.isoformat(),
        "reminder_time": "08:30",
        "deadline": "2026-12-01",
    }
    assert unapplied(todo, tags=["@phone"], when="today@8:30") == []
    assert unapplied(todo, when="next week", deadline="friday") == []
    assert unapplied(
        todo,
        list_id="P1",
        tags=["@phone", "@home"],
        when=f"{today + timedelta(1)}@09:00",
        deadline="2026-12-02",
    ) == [
        "project (filed in Today)",
        "tags (@home missing)",
        f"when (Things shows {today})",
        "reminder (Things shows 08:30)",
        "deadline (Things shows 2026-12-01)",
    ]
    assert unapplied(todo, when="someday") == ["when (Things shows Today)"]
