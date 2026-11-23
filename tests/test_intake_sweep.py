"""COS-279: process-inbox all=True include_today sweeps Inbox and Today in one call."""

import datetime

import pytest

from tests.conftest import create_mock_todo, tool_text


def _days_ago(n):
    return (
        datetime.date.today() - datetime.timedelta(days=n)
    ).isoformat() + " 09:00:00"


@pytest.fixture
def process_inbox(monkeypatch, mock_utils):
    inbox = [create_mock_todo(uuid_str="I1", title="Voice: call bank")]
    inbox[0]["created"] = _days_ago(3)
    today = [
        create_mock_todo(uuid_str="T1", title="Buy cable"),
        dict(create_mock_todo(uuid_str="P1", title="A project"), type="project"),
        dict(inbox[0]),  # already in the inbox: not listed twice
    ]
    today[0]["created"] = _days_ago(0)
    monkeypatch.setattr("things_mcp.reader.inbox", lambda: inbox)
    monkeypatch.setattr("things_mcp.reader.today", lambda: today)
    from things_mcp.fast_server import mcp

    return mcp._local_provider._components["tool:process-inbox@"].fn


@pytest.mark.asyncio
async def test_one_call_returns_both_lists_with_ages(process_inbox):
    result = await process_inbox(all=True, include_today=True)
    data = result.structured_content["data"]
    assert [(d["uuid"], d["bucket"], d["age_days"]) for d in data] == [
        ("I1", "Inbox", 3),
        ("T1", "Today", 0),
    ]
    assert "Inbox and Today: 2 items" in tool_text(result)


@pytest.mark.asyncio
async def test_without_flag_inbox_only(process_inbox):
    result = await process_inbox(all=True)
    data = result.structured_content["data"]
    assert [d["uuid"] for d in data] == ["I1"]
    assert data[0]["age_days"] == 3


@pytest.mark.asyncio
async def test_today_items_count_when_inbox_is_empty(monkeypatch, process_inbox):
    monkeypatch.setattr("things_mcp.reader.inbox", lambda: [])
    result = await process_inbox(all=True, include_today=True)
    data = result.structured_content["data"]
    assert [(d["uuid"], d["bucket"]) for d in data] == [
        ("T1", "Today"),
        ("I1", "Today"),
    ]


def test_output_schema_is_one_list_shape():
    """process-inbox advertises one shape: the anyOf flattener used to keep only
    the Todo branch of a Todo | list union, so every all=True result failed
    validation at the Cloudflare portal (COS-279)."""
    from things_mcp.models import SweepItem, ToolEnvelope, output_schema_for
    from things_mcp.server_core import _flatten_anyof_for_n8n

    flat = _flatten_anyof_for_n8n(output_schema_for(ToolEnvelope[list[SweepItem]]))
    assert "array" in flat["properties"]["data"]["type"]


def test_payload_dumps_use_the_list_alias():
    """Review payloads dumped without by_alias leaked `list_label`, which the
    output schema forbids, so the portal rejected daily-review, weekly-review
    and focus-mode results (COS-279)."""
    import pathlib

    src = pathlib.Path(__file__).parents[1] / "src" / "things_mcp"
    leaks = [p.name for p in src.glob("tools_*.py") if ".model_dump()" in p.read_text()]
    assert leaks == []
