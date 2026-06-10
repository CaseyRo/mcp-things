"""MCP resources: ambient, read-only GTD context under the ``things://`` scheme.

Resources let an agent passively pull current GTD state (inbox count, today's
list, stalled projects, triage stats) and static reference data (the GTD context
tag taxonomy, server config) *without spending a tool call*. They mirror data the
review tools already compute — they just expose it as addressable, cacheable
context the model can read on its own initiative.

All resources are read-only by definition. Mutations still go through the
existing ``@mcp.tool`` write tools.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastmcp import FastMCP

from . import reader as db
from .logging_config import get_logger
from .settings import get_settings, get_transport
from .triage_tracker import triage_tracker

logger = get_logger(__name__)


# GTD context tags shipped as a discoverable taxonomy. Mirrors the contexts
# documented in the server instructions and CLAUDE.md.
GTD_CONTEXT_TAGS: list[dict[str, str]] = [
    {"tag": "@computer", "meaning": "Anything requiring a computer / desk."},
    {"tag": "@phone", "meaning": "Calls or tasks done on the phone."},
    {"tag": "@office", "meaning": "Requires being at the office."},
    {"tag": "@home", "meaning": "Requires being at home."},
    {"tag": "@errands", "meaning": "Out-and-about tasks (shops, post, bank)."},
    {"tag": "@anywhere", "meaning": "Context-free; can be done from anywhere."},
    {
        "tag": "waiting-for",
        "meaning": "Delegated — awaiting someone else (see delegate-task).",
    },
]


def _stalled_projects(today_str: str) -> list[dict[str, str]]:
    """Return incomplete projects that have no available next action.

    Mirrors the weekly-review stalled-project computation: a project is stalled
    when none of its incomplete to-dos are available (anytime / today / no start).
    """
    from collections import defaultdict

    projects = db.projects() or []
    all_incomplete = db.todos(status="incomplete") or []

    todos_by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in all_incomplete:
        proj_uuid = t.get("project")
        if proj_uuid:
            todos_by_project[proj_uuid].append(t)

    stalled: list[dict[str, str]] = []
    for project in projects:
        if project.get("status") != "incomplete":
            continue
        proj_todos = todos_by_project.get(project.get("uuid"), [])
        available = [
            t
            for t in proj_todos
            if t.get("start") in (None, "Anytime", "Today")
            or t.get("start_date") is None
            or t.get("start_date") == today_str
        ]
        if not available:
            stalled.append(
                {"uuid": project.get("uuid", ""), "title": project.get("title", "")}
            )
    return stalled


def register_resources(mcp: FastMCP) -> None:
    """Register ambient GTD-state and reference resources with the server."""

    @mcp.resource(
        "things://inbox/count",
        name="inbox-count",
        title="Inbox Count",
        description="Number of unclarified items currently in the Things inbox.",
        mime_type="application/json",
        tags={"reflect", "ambient"},
    )
    def inbox_count() -> str:
        inbox = db.inbox() or []
        return json.dumps({"inbox_count": len(inbox)})

    @mcp.resource(
        "things://today",
        name="today",
        title="Today's Tasks",
        description=(
            "Today's scheduled tasks plus overdue items — the GTD 'hard "
            "landscape' for right now. Read this to orient before planning a day."
        ),
        mime_type="application/json",
        tags={"engage", "reflect", "ambient"},
    )
    def today() -> str:
        today_str = date.today().isoformat()
        today_tasks = db.today() or []
        all_todos = db.todos(status="incomplete") or []
        overdue = [
            {"title": t.get("title", ""), "deadline": t.get("deadline")}
            for t in all_todos
            if t.get("deadline") and t.get("deadline") < today_str
        ]
        return json.dumps(
            {
                "date": today_str,
                "today_count": len(today_tasks),
                "overdue_count": len(overdue),
                "today": [t.get("title", "") for t in today_tasks],
                "overdue": overdue,
            }
        )

    @mcp.resource(
        "things://stalled-projects",
        name="stalled-projects",
        title="Stalled Projects",
        description=(
            "Incomplete projects with no available next action — the core "
            "weekly-review signal. Each stalled project needs a next action added."
        ),
        mime_type="application/json",
        tags={"reflect", "organize", "ambient"},
    )
    def stalled_projects() -> str:
        today_str = date.today().isoformat()
        stalled = _stalled_projects(today_str)
        return json.dumps({"stalled_count": len(stalled), "projects": stalled})

    @mcp.resource(
        "things://triage/stats",
        name="triage-stats",
        title="Triage Stats (7 days)",
        description=(
            "Anonymised triage activity over the last 7 days: totals, action "
            "breakdown, busiest day, and the no-context cancel rate. No task "
            "titles or content are stored."
        ),
        mime_type="application/json",
        tags={"reflect", "ambient", "stats"},
    )
    def triage_stats() -> str:
        try:
            summary = triage_tracker.get_summary(days=7)
        except Exception:
            logger.debug("triage stats resource failed (non-critical)", exc_info=True)
            summary = {"total": 0}
        return json.dumps(summary)

    @mcp.resource(
        "things://contexts",
        name="gtd-contexts",
        title="GTD Context Tags",
        description=(
            "The GTD context-tag taxonomy this server recognises (@computer, "
            "@phone, …). Use these with get-tasks(context=…) to filter by where "
            "or how a task can be done."
        ),
        mime_type="application/json",
        tags={"reference", "taxonomy"},
    )
    def gtd_contexts() -> str:
        return json.dumps({"contexts": GTD_CONTEXT_TAGS})

    @mcp.resource(
        "things://config",
        name="server-config",
        title="Server Config",
        description=(
            "Non-secret server configuration: host, port, transport, and "
            "whether a Things auth token is configured (needed for writes). "
            "Secrets are never exposed."
        ),
        mime_type="application/json",
        tags={"reference", "status"},
    )
    def server_config() -> str:
        settings = get_settings()
        try:
            from . import __version__ as version
        except ImportError:
            version = "unknown"
        token = settings.things_auth_token.get_secret_value()
        return json.dumps(
            {
                "version": version,
                "host": settings.things_mcp_host,
                "port": settings.things_mcp_port,
                "transport": get_transport(),
                "auth_token_configured": bool(token),
            }
        )
