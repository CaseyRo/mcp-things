"""Server-side repeating to-dos (CDI-2076): rules, next occurrence, sweep, tools."""

from datetime import date
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from fastmcp import Client

from things_mcp import repeat
from things_mcp.repeat import next_date, parse_rule, plan_next, rule_in, with_rule

SAT2 = parse_rule("monthly:2nd-saturday")


def _next(rule: str, after: str) -> str:
    return next_date(parse_rule(rule), date.fromisoformat(after)).isoformat()


# -- rule parsing -------------------------------------------------------------


@pytest.mark.parametrize(
    "text, canonical",
    [
        ("monthly:2nd-saturday", "monthly:2nd-saturday fixed"),
        ("Monthly:2nd-Sat after-completion", "monthly:2nd-sat after-completion"),
        ("weekly:mon,thu", "weekly:mon,thu fixed"),
        ("every:14d", "every:14d fixed"),
        ("daily", "every:1d fixed"),
        ("monthly:last", "monthly:last fixed"),
    ],
)
def test_parse_valid(text, canonical):
    assert parse_rule(text).text == canonical


@pytest.mark.parametrize(
    "text",
    [
        "",
        "fortnightly",
        "every:0d",
        "every:3x",
        "weekly:",
        "weekly:funday",
        "monthly:32",
        "monthly:6th-monday",
        "monthly:2nd-saturday sometimes",
    ],
)
def test_parse_invalid_names_the_grammar(text):
    with pytest.raises(ValueError, match="monthly:2nd-saturday"):
        parse_rule(text)


# -- next occurrence ------------------------------------------------------------


@pytest.mark.parametrize(
    "after, expected",
    [
        ("2026-11-14", "2026-12-12"),  # CDiT OS update: Nov -> Dec
        ("2026-12-12", "2027-01-09"),  # Dec -> Jan, across the year
        ("2027-01-09", "2027-02-13"),  # into February
        ("2026-11-01", "2026-11-14"),  # same month, before the 2nd Saturday
        ("2026-07-11", "2026-08-08"),  # August 2026 has five Saturdays
    ],
)
def test_second_saturday(after, expected):
    assert _next("monthly:2nd-saturday", after) == expected


def test_other_month_rules():
    assert _next("monthly:last-saturday", "2026-08-01") == "2026-08-29"
    assert _next("monthly:5th-saturday", "2026-08-01") == "2026-08-29"
    assert _next("monthly:5th-saturday", "2026-08-29") == "2026-10-31"  # Sep has 4
    assert _next("monthly:31", "2027-01-31") == "2027-02-28"  # clamps to Feb
    assert _next("monthly:last", "2028-02-01") == "2028-02-29"  # leap year


def test_interval_and_weekly_rules():
    assert _next("every:14d", "2026-12-25") == "2027-01-08"
    assert _next("every:1m", "2027-01-31") == "2027-02-28"
    assert _next("every:1y", "2028-02-29") == "2029-02-28"
    assert _next("weekly:mon,thu", "2026-10-24") == "2026-10-26"  # Sat -> Mon
    assert _next("weekly:mon,thu", "2026-10-26") == "2026-10-29"  # Mon -> Thu


# -- notes marker ---------------------------------------------------------------


def test_marker_round_trip_keeps_notes():
    notes = with_rule("Runbook: docs/x.md", SAT2)
    assert notes.startswith("Runbook: docs/x.md\n\n🔁 repeat: monthly:2nd-saturday")
    assert rule_in(notes) == SAT2
    changed = with_rule(notes, parse_rule("every:14d"))
    assert changed.count("🔁 repeat:") == 1 and rule_in(changed).spec == "every:14d"
    assert with_rule(notes, None) == "Runbook: docs/x.md"


# -- planning the next occurrence ------------------------------------------------

CDIT_ROW = {
    "uuid": "done-1",
    "title": "CDiT OS update (monthly)",
    "notes": with_rule("Runbook: docs/cdit-os-update.md", SAT2),
    "start": "Someday",
    "start_date": "2026-11-14",
    "deadline": "2026-11-15",
    "stop_date": "2026-11-14 18:02:11",
    "tags": ["@computer", "CDIT"],
    "checklist": [
        {"title": "Backups first", "status": "completed"},
        {"title": "Publish the report artifact", "status": "completed"},
    ],
    "area": "area-cdit",
}


def test_plan_next_carries_everything_over():
    nxt = plan_next(CDIT_ROW, SAT2)
    assert nxt == {
        "title": "CDiT OS update (monthly)",
        "notes": CDIT_ROW["notes"],
        "when": "2026-12-12",
        "deadline": "2026-12-13",
        "tags": ["@computer", "CDIT"],
        "checklist_items": ["Backups first", "Publish the report artifact"],
        "list_id": "area-cdit",
        "heading": None,
    }


def test_plan_next_completed_late_skips_past_dates():
    nxt = plan_next({**CDIT_ROW, "stop_date": "2027-01-03 10:00:00"}, SAT2)
    assert (nxt["when"], nxt["deadline"]) == ("2027-01-09", "2027-01-10")


def test_plan_next_after_completion_counts_from_completion_day():
    rule = parse_rule("every:14d after-completion")
    nxt = plan_next({**CDIT_ROW, "stop_date": "2026-11-20 09:00:00"}, rule)
    assert (nxt["when"], nxt["deadline"]) == ("2026-12-04", "2026-12-05")


# -- sweep ----------------------------------------------------------------------


@pytest.fixture
def sweep_env(monkeypatch, tmp_path):
    rows: list[dict] = []
    monkeypatch.setattr(
        "things_mcp.reader.logbook_with_notes", lambda fragment: list(rows)
    )
    execute = mock.Mock(return_value=True)
    monkeypatch.setattr("things_mcp.url_scheme.execute_url", execute)
    monkeypatch.setattr("things_mcp.url_scheme.construct_url", _url)
    return SimpleNamespace(rows=rows, execute=execute, state=tmp_path / "state.json")


def _url(command, params):
    """construct_url without the auth-token lookup."""
    return f"things:///{command}?{urlencode(params)}"


def test_sweep_creates_exactly_one_next_occurrence(sweep_env):
    old = {**CDIT_ROW, "uuid": "done-before-deploy"}
    sweep_env.rows.append(old)
    # First run adopts the existing logbook without replaying it.
    assert repeat.sweep(sweep_env.state) == []
    sweep_env.execute.assert_not_called()

    sweep_env.rows.append(CDIT_ROW)
    created = repeat.sweep(sweep_env.state)
    assert [(c["when"], c["deadline"]) for c in created] == [
        ("2026-12-12", "2026-12-13")
    ]
    assert sweep_env.execute.call_count == 1

    # Later sweeps and a restart (fresh read of the same state file) are no-ops.
    assert repeat.sweep(sweep_env.state) == []
    assert repeat.sweep(sweep_env.state) == []
    assert sweep_env.execute.call_count == 1


def test_sweep_retries_when_the_write_fails(sweep_env):
    repeat.sweep(sweep_env.state)  # baseline
    sweep_env.rows.append(CDIT_ROW)
    sweep_env.execute.return_value = False
    assert repeat.sweep(sweep_env.state) == []
    sweep_env.execute.return_value = True
    assert len(repeat.sweep(sweep_env.state)) == 1
    assert repeat.sweep(sweep_env.state) == []


# -- tools over the protocol ------------------------------------------------------


@pytest.fixture
def write_path(monkeypatch):
    execute = mock.Mock(return_value=True)
    monkeypatch.setattr("things_mcp.tools_gtd_organize.execute_url", execute)
    monkeypatch.setattr(
        "things_mcp.tools_gtd_organize.app_state",
        mock.Mock(update_app_state=mock.Mock(return_value=True)),
    )
    monkeypatch.setattr(
        "things_mcp.tools_gtd_organize.ensure_tags_exist", mock.Mock(return_value=True)
    )
    monkeypatch.setattr("things_mcp.tools_gtd_organize.record_write", mock.Mock())
    monkeypatch.setattr("things_mcp.tools_gtd_organize.triage_tracker", mock.Mock())
    monkeypatch.setattr("things_mcp.url_scheme.construct_url", _url)
    return execute


def _sent(execute) -> dict:
    url = urlparse(execute.call_args.args[0])
    return {k: v[0] for k, v in parse_qs(url.query).items()}


async def test_schedule_task_repeat_over_the_protocol(write_path):
    from things_mcp.fast_server import mcp

    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert "repeat" in tools["schedule-task"].input_schema["properties"]
        assert "repeat" in tools["modify-task"].input_schema["properties"]

        result = await client.call_tool(
            "schedule-task",
            {
                "title": "CDiT OS update (monthly)",
                "when": "2026-11-14",
                "deadline": "2026-11-15",
                "notes": "Runbook",
                "repeat": "monthly:2nd-saturday",
            },
        )
        assert not result.is_error
        assert "server-side repeat" in result.content[0].text
        assert result.structured_content["meta"]["repeat_kind"] == "server-side"
        sent = _sent(write_path)
        assert rule_in(sent["notes"]) == SAT2
        assert sent["notes"].startswith("Runbook\n\n🔁 repeat:")

        bad = await client.call_tool(
            "schedule-task",
            {"title": "x", "when": "today", "repeat": "fortnightly"},
            raise_on_error=False,
        )
        assert bad.is_error and "monthly:2nd-saturday" in bad.content[0].text


async def test_modify_task_sets_and_clears_repeat(write_path, monkeypatch):
    from things_mcp.fast_server import mcp

    todo = {"uuid": "9LQY", "type": "to-do", "title": "T", "notes": "Keep me"}
    monkeypatch.setattr(
        "things_mcp.tools_gtd_organize.things", SimpleNamespace(get=lambda _id: todo)
    )
    monkeypatch.setattr("things_mcp.reader.is_native_repeat", lambda _id: False)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "modify-task", {"task_id": "9LQY", "repeat": "monthly:2nd-saturday"}
        )
        assert "server-side repeat" in result.content[0].text
        sent = _sent(write_path)
        assert sent["notes"].startswith("Keep me\n\n🔁 repeat: monthly:2nd-saturday")
        assert "when" not in sent and "deadline" not in sent

        todo["notes"] = sent["notes"]
        await client.call_tool("modify-task", {"task_id": "9LQY", "repeat": "none"})
        assert _sent(write_path)["notes"] == "Keep me"

        monkeypatch.setattr("things_mcp.reader.is_native_repeat", lambda _id: True)
        native = await client.call_tool(
            "modify-task",
            {"task_id": "9LQY", "repeat": "weekly:mon"},
            raise_on_error=False,
        )
        assert native.is_error and "natively" in native.content[0].text


def test_formatters_show_the_rule():
    from things_mcp.formatters import render_todo, to_dict_todo

    row = {**CDIT_ROW, "type": "to-do", "status": "incomplete", "checklist": []}
    assert to_dict_todo(row)["repeat"] == "monthly:2nd-saturday fixed"
    assert "Repeat: monthly:2nd-saturday fixed (server-side)" in render_todo(row)
    assert to_dict_todo({**row, "notes": "plain"})["repeat"] is None
