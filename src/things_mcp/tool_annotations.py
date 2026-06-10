"""Shared tool annotations for Things MCP tools.

This module contains the annotation dictionaries used by all tool modules
to specify tool behavior hints (read-only, destructive, idempotent, etc.),
human-friendly display titles, and read/write/destructive tags.

Annotation semantics (per the MCP spec — all hints are advisory):

- ``readOnlyHint=True``   → the tool does not mutate any state (get-*/search-*/
  show-*/review/insights). Reads are also idempotent.
- ``destructiveHint=True``→ re-running or running the tool performs an
  irreversible-ish change (delete-area, merge-areas, bulk-cancel). Note that
  ``complete-task`` is reversible in Things 3, so it is *not* destructive — it
  is idempotent instead (completing an already-complete task is a no-op).
- ``idempotentHint=True`` → running the tool again with the same args has no
  additional effect (modify/schedule/defer/complete and their bulk forms).
- ``openWorldHint=False`` → Things is a *local* macOS app, not an external or
  open-world system, so this is False on every tool.

Tags are coarse capability buckets surfaced to clients: ``read``, ``write``,
and ``destructive``. They are additive metadata; existing parameters and
return shapes are unchanged.
"""

from typing import Dict, Set

import mcp.types as types


# ---------------------------------------------------------------------------
# Annotation factories — one ToolAnnotations per tool so each carries its own
# human-friendly `title`. The boolean hints below mirror the four buckets the
# server used before this deepening pass; only `title` is newly populated.
# ---------------------------------------------------------------------------


def _read_only(title: str) -> types.ToolAnnotations:
    """Read tool: no mutation, idempotent, local app."""
    return types.ToolAnnotations(
        title=title,
        readOnlyHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )


def _add(title: str) -> types.ToolAnnotations:
    """Create tool: mutates, not idempotent (re-running creates duplicates)."""
    return types.ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )


def _update(title: str) -> types.ToolAnnotations:
    """Update tool: mutates, idempotent, not destructive."""
    return types.ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


def _destructive(title: str) -> types.ToolAnnotations:
    """Destructive tool: irreversible-ish mutation (delete/cancel/merge)."""
    return types.ToolAnnotations(
        title=title,
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )


# Backwards-compatible module constants (previously a single shared instance
# per bucket). Kept so any external importer still resolves the names; these
# carry no per-tool title.
READ_ONLY_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=False,
)

ADD_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)

UPDATE_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

DESTRUCTIVE_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)


TOOL_ANNOTATIONS: Dict[str, types.ToolAnnotations] = {
    # === GTD Engage Tools ===
    "get-tasks": _read_only("Get Tasks"),
    "focus-mode": _read_only("Focus Mode"),
    # complete-task is reversible in Things 3 → idempotent, not destructive.
    "complete-task": _update("Complete Task"),
    # === GTD Capture Tools ===
    "capture-task": _add("Capture Task"),
    # === GTD Clarify Tools ===
    "process-inbox": _read_only("Process Inbox"),
    "convert-to-project": _add("Convert Task to Project"),
    # === GTD Organize Tools ===
    "schedule-task": _add("Schedule Task"),
    "delegate-task": _update("Delegate Task"),
    "defer-task": _update("Defer Task"),
    "plan-project": _add("Plan Project"),
    "modify-task": _update("Modify Task"),
    "create-area": _add("Create Area"),
    "modify-project": _update("Modify Project"),
    "modify-area": _update("Modify Area"),
    "delete-area": _destructive("Delete Area"),
    "merge-areas": _destructive("Merge Areas"),
    # === GTD Reflect Tools ===
    "daily-review": _read_only("Daily Review"),
    "weekly-review": _read_only("Weekly Review"),
    # === Utility Tools ===
    "search-tasks": _read_only("Search Tasks"),
    "get-projects": _read_only("Get Projects"),
    "get-areas": _read_only("Get Areas"),
    "get-project": _read_only("Get Project"),
    "get-area": _read_only("Get Area"),
    "get-tags": _read_only("Get Tags"),
    "show-in-app": _read_only("Show in Things App"),
    "get-cache-stats": _read_only("Get Cache Stats"),
    "triage-insights": _read_only("Triage Insights"),
    # === Batch Tools ===
    "bulk-capture": _add("Bulk Capture Tasks"),
    "bulk-complete": _update("Bulk Complete Tasks"),
    "bulk-cancel": _destructive("Bulk Cancel Tasks"),
    "bulk-modify": _update("Bulk Modify Tasks"),
    "bulk-triage": _update("Bulk Triage Inbox"),
}


# ---------------------------------------------------------------------------
# Coarse capability tags per tool. `read` = no mutation, `write` = mutates,
# `destructive` = irreversible-ish mutation (always paired with `write`).
# ---------------------------------------------------------------------------

_READ: Set[str] = {"read"}
_WRITE: Set[str] = {"write"}
_DESTRUCTIVE: Set[str] = {"write", "destructive"}

TOOL_TAGS: Dict[str, Set[str]] = {
    # === GTD Engage Tools ===
    "get-tasks": set(_READ),
    "focus-mode": set(_READ),
    "complete-task": set(_WRITE),
    # === GTD Capture Tools ===
    "capture-task": set(_WRITE),
    # === GTD Clarify Tools ===
    "process-inbox": set(_READ),
    "convert-to-project": set(_WRITE),
    # === GTD Organize Tools ===
    "schedule-task": set(_WRITE),
    "delegate-task": set(_WRITE),
    "defer-task": set(_WRITE),
    "plan-project": set(_WRITE),
    "modify-task": set(_WRITE),
    "create-area": set(_WRITE),
    "modify-project": set(_WRITE),
    "modify-area": set(_WRITE),
    "delete-area": set(_DESTRUCTIVE),
    "merge-areas": set(_DESTRUCTIVE),
    # === GTD Reflect Tools ===
    "daily-review": set(_READ),
    "weekly-review": set(_READ),
    # === Utility Tools ===
    "search-tasks": set(_READ),
    "get-projects": set(_READ),
    "get-areas": set(_READ),
    "get-project": set(_READ),
    "get-area": set(_READ),
    "get-tags": set(_READ),
    "show-in-app": set(_READ),
    "get-cache-stats": set(_READ),
    "triage-insights": set(_READ),
    # === Batch Tools ===
    "bulk-capture": set(_WRITE),
    "bulk-complete": set(_WRITE),
    "bulk-cancel": set(_DESTRUCTIVE),
    "bulk-modify": set(_WRITE),
    "bulk-triage": set(_WRITE),
}


def tags_for(name: str) -> Set[str]:
    """Return a fresh copy of the capability tags for a tool.

    Returns a new set so callers (the ``@mcp.tool(tags=...)`` registrations)
    never share or mutate the module-level definition.
    """
    return set(TOOL_TAGS.get(name, set()))
