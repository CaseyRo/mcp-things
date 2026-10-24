"""Helpers that build `ToolResult` objects for tool returns.

Tools call `make_result(...)`, `write_result(...)`, or `bulk_result(...)` to
construct a FastMCP `ToolResult` with a uniform `ToolEnvelope` in
`structured_content` and a `TextContent` block in `content`. This keeps
existing text-only clients (Claude Desktop's readable view, prompt logs)
working byte-for-byte, while machine consumers get the JSON envelope.

The text block is *explicit* — never auto-derived. FastMCP's auto-derivation
emits the structured payload as raw JSON, which would regress every
human-facing surface.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from fastmcp.tools import ToolResult
from mcp.types import TextContent

from .formatters import to_dict_todo
from .models import (
    BulkItemError,
    BulkResult,
    ToolEnvelope,
    WriteResult,
)


def make_result(
    *,
    data: Any,
    summary: str,
    meta: dict[str, Any] | None = None,
    text: str | None = None,
) -> ToolResult:
    """Build a `ToolResult` with envelope `structured_content` and text fallback.

    Args:
        data: The structured payload (Pydantic model, list, dict, or None).
        summary: One-sentence machine-readable headline.
        meta: Optional metadata bag. Defaults to empty.
        text: Human-readable text block. Defaults to `summary` when omitted.

    Returns:
        A `ToolResult` whose `structured_content` is the envelope's JSON
        serialisation, and whose `content` is a single `TextContent` block.
    """
    envelope = ToolEnvelope(data=data, summary=summary, meta=meta or {})
    text_body = text if text is not None else summary
    return ToolResult(
        content=[TextContent(type="text", text=text_body)],
        # `by_alias=True` so fields with serialization aliases (e.g. Todo.list)
        # emit the alias as the JSON key.
        structured_content=envelope.model_dump(mode="json", by_alias=True),
    )


def write_result(
    *,
    summary: str,
    thing_id: str | None = None,
    acknowledged: bool = True,
    meta: dict[str, Any] | None = None,
    text: str | None = None,
) -> ToolResult:
    """Build a `ToolResult` for a write tool (capture, schedule, modify, ...)."""
    payload = WriteResult(
        acknowledged=acknowledged,
        thing_id=thing_id,
        summary=summary,
    )
    return make_result(data=payload, summary=summary, meta=meta, text=text)


NOT_CONFIRMED = (
    "Created, not yet confirmed: Things had not written it to its database "
    "within a few seconds, so there is no thing_id yet; check with search-tasks."
)


def unapplied(
    todo: dict[str, Any],
    *,
    list_id: str | None = None,
    list_type: str = "project",
    tags: list[str] | None = None,
    when: str | None = None,
    deadline: str | None = None,
) -> list[str]:
    """Requested fields the read-back to-do does not show (CDI-1588).

    Only checks what can be compared exactly; a natural-language ``when``
    ("next week") is not second-guessed.
    """
    misses = []
    if list_id and todo.get(list_type) != list_id:
        misses.append(f"{list_type} (filed in {todo['list']})")
    have = {t.casefold() for t in todo["tags"]}
    missing = [t for t in tags or [] if t.casefold() not in have]
    if missing:
        misses.append(f"tags ({', '.join(missing)} missing)")
    day, _, at = (when or "").partition("@")
    day = day.strip().lower()
    today = date.today()
    expected = {"today": today, "evening": today, "tomorrow": today + timedelta(1)}
    want = expected.get(day) or _iso(day)
    if want and todo["start_date"] != want.isoformat():
        misses.append(f"when (Things shows {todo['start_date'] or todo['list']})")
    elif day == "someday" and todo["start"] != "Someday":
        misses.append(f"when (Things shows {todo['list']})")
    if re.fullmatch(r"\d{1,2}:\d{2}", at) and todo["reminder_time"] != at.zfill(5):
        misses.append(f"reminder (Things shows {todo['reminder_time'] or 'none'})")
    if _iso(deadline) and todo["deadline"] != deadline:
        misses.append(f"deadline (Things shows {todo['deadline'] or 'none'})")
    return misses


def _iso(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


def readback(row: dict[str, Any] | None, **requested: Any) -> tuple[str, dict]:
    """A create's confirmation sentence and meta from its read-back row."""
    if row is None:
        return NOT_CONFIRMED, {"confirmed": False}
    todo = to_dict_todo(row)
    misses = unapplied(todo, **requested)
    note = f"Confirmed in Things, filed in {todo['list']}"
    note += f", start date {todo['start_date']}." if todo["start_date"] else "."
    if misses:
        note += f" NOT applied: {'; '.join(misses)}."
    return note, {"confirmed": True, "unapplied": misses, "todo": todo}


def bulk_result(
    *,
    requested: int,
    succeeded_ids: list[str],
    failed_ids: list[str],
    errors: list[BulkItemError],
    summary: str,
    by_action: dict[str, int] | None = None,
    meta: dict[str, Any] | None = None,
    text: str | None = None,
) -> ToolResult:
    """Build a `ToolResult` for a bulk tool with per-item fault detail."""
    payload = BulkResult(
        requested=requested,
        succeeded=len(succeeded_ids),
        failed=len(failed_ids) + sum(1 for e in errors if e.task_id is None),
        succeeded_ids=succeeded_ids,
        failed_ids=failed_ids,
        errors=errors,
        by_action=by_action or {},
    )
    return make_result(data=payload, summary=summary, meta=meta, text=text)
