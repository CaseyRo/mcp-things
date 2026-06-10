"""Contract tests for ToolAnnotations, titles, and capability tags.

Deepening pass (KIND=annotations): every one of the 32 tools must carry

- a populated, human-friendly ``annotations.title``
- semantically correct behavior hints (readOnly / destructive / idempotent /
  ``openWorldHint=False`` because Things is a *local* macOS app)
- coarse read/write/destructive capability tags consistent with those hints

These tests run without Things 3 — they only introspect tool registration via
``mcp.list_tools()`` and the ``TOOL_ANNOTATIONS`` / ``TOOL_TAGS`` source of
truth, so they are CI-safe.
"""

from __future__ import annotations

import pytest

from things_mcp.fast_server import mcp
from things_mcp.tool_annotations import (
    TOOL_ANNOTATIONS,
    TOOL_TAGS,
    tags_for,
)


EXPECTED_TOOL_COUNT = 32

# Tools that perform irreversible-ish mutations (delete / cancel / merge).
# complete-task is intentionally NOT here: completing is reversible in Things 3.
DESTRUCTIVE_TOOLS = {"delete-area", "merge-areas", "bulk-cancel"}

# Read-only tools: get-*, search-*, show-*, *-review, *-insights, process-inbox.
READ_ONLY_TOOLS = {
    "get-tasks",
    "focus-mode",
    "process-inbox",
    "daily-review",
    "weekly-review",
    "search-tasks",
    "get-projects",
    "get-areas",
    "get-project",
    "get-area",
    "get-tags",
    "show-in-app",
    "get-cache-stats",
    "triage-insights",
}


async def _tools_by_name():
    """All tools registered on the live server, keyed by name."""
    tools = await mcp.list_tools()
    return {t.name: t for t in tools}


# ---------------------------------------------------------------------------
# Coverage: every tool is annotated, titled, and tagged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_tool_has_annotations_title_and_tags():
    tools = await _tools_by_name()
    assert len(tools) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, found {len(tools)}"
    )

    missing_annotations = []
    missing_title = []
    missing_tags = []
    for name, tool in tools.items():
        ann = tool.annotations
        if ann is None:
            missing_annotations.append(name)
            continue
        if not getattr(ann, "title", None):
            missing_title.append(name)
        if not getattr(tool, "tags", None):
            missing_tags.append(name)

    assert not missing_annotations, f"Tools with no annotations: {missing_annotations}"
    assert not missing_title, f"Tools with no annotation title: {missing_title}"
    assert not missing_tags, f"Tools with no tags: {missing_tags}"


@pytest.mark.asyncio
async def test_open_world_hint_false_everywhere():
    """Things is a LOCAL macOS app — openWorldHint must be False on every tool."""
    tools = await _tools_by_name()
    offenders = [
        name
        for name, tool in tools.items()
        if tool.annotations is None or tool.annotations.openWorldHint is not False
    ]
    assert not offenders, (
        f"openWorldHint must be False (local app) but these tools differ: {offenders}"
    )


# ---------------------------------------------------------------------------
# Semantics: read-only / destructive / idempotent hints match tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_only_tools_are_read_only_and_tagged_read():
    tools = await _tools_by_name()
    for name in READ_ONLY_TOOLS:
        tool = tools[name]
        ann = tool.annotations
        assert ann.readOnlyHint is True, f"{name} should set readOnlyHint=True"
        assert "read" in tool.tags, f"{name} should carry the 'read' tag"
        assert "write" not in tool.tags, f"{name} must NOT carry the 'write' tag"
        assert "destructive" not in tool.tags, (
            f"{name} must NOT carry the 'destructive' tag"
        )


@pytest.mark.asyncio
async def test_destructive_tools_flagged_and_tagged():
    tools = await _tools_by_name()
    for name in DESTRUCTIVE_TOOLS:
        tool = tools[name]
        ann = tool.annotations
        assert ann.destructiveHint is True, f"{name} should set destructiveHint=True"
        assert ann.readOnlyHint is False, f"{name} must not be readOnly"
        assert {"write", "destructive"} <= set(tool.tags), (
            f"{name} should carry both 'write' and 'destructive' tags, got {tool.tags}"
        )


@pytest.mark.asyncio
async def test_complete_task_is_idempotent_not_destructive():
    """complete-task is reversible in Things 3 → idempotent, never destructive."""
    tools = await _tools_by_name()
    ann = tools["complete-task"].annotations
    assert ann.idempotentHint is True
    assert ann.destructiveHint in (False, None)
    assert "destructive" not in tools["complete-task"].tags
    assert "write" in tools["complete-task"].tags


@pytest.mark.asyncio
async def test_write_tools_never_read_only():
    """Any tool tagged 'write' must not also claim readOnlyHint=True."""
    tools = await _tools_by_name()
    offenders = [
        name
        for name, tool in tools.items()
        if "write" in tool.tags and tool.annotations.readOnlyHint is True
    ]
    assert not offenders, f"Write tools wrongly marked readOnly: {offenders}"


# ---------------------------------------------------------------------------
# Source-of-truth maps stay in lockstep with the registered tool set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_annotation_and_tag_maps_cover_exactly_the_registered_tools():
    tools = await _tools_by_name()
    registered = set(tools)
    assert set(TOOL_ANNOTATIONS) == registered, (
        "TOOL_ANNOTATIONS keys drifted from the registered tools: "
        f"missing={registered - set(TOOL_ANNOTATIONS)}, "
        f"extra={set(TOOL_ANNOTATIONS) - registered}"
    )
    assert set(TOOL_TAGS) == registered, (
        "TOOL_TAGS keys drifted from the registered tools: "
        f"missing={registered - set(TOOL_TAGS)}, "
        f"extra={set(TOOL_TAGS) - registered}"
    )


def test_tags_for_returns_a_fresh_copy():
    """tags_for must not hand out the shared module-level set (mutation safety)."""
    a = tags_for("delete-area")
    b = tags_for("delete-area")
    assert a == b == {"write", "destructive"}
    a.add("mutated")
    assert "mutated" not in tags_for("delete-area")
    assert "mutated" not in TOOL_TAGS["delete-area"]
