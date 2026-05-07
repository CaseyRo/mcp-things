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

from typing import Any

from fastmcp.tools import ToolResult
from mcp.types import TextContent

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
        structured_content=envelope.model_dump(mode="json"),
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
