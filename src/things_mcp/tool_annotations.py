"""Shared tool annotations for Things MCP tools.

This module contains the annotation dictionaries used by all tool modules
to specify tool behavior hints (read-only, destructive, idempotent, etc.).
"""

from typing import Dict
import mcp.types as types

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

TOOL_ANNOTATIONS: Dict[str, types.ToolAnnotations] = {
    # === GTD Engage Tools ===
    "get-tasks": READ_ONLY_ANNOTATIONS,
    "focus-mode": READ_ONLY_ANNOTATIONS,
    "complete-task": UPDATE_ANNOTATIONS,
    # === GTD Capture Tools ===
    "capture-task": ADD_ANNOTATIONS,
    # === GTD Clarify Tools ===
    "process-inbox": READ_ONLY_ANNOTATIONS,
    "convert-to-project": ADD_ANNOTATIONS,
    # === GTD Organize Tools ===
    "schedule-task": ADD_ANNOTATIONS,
    "delegate-task": UPDATE_ANNOTATIONS,
    "defer-task": UPDATE_ANNOTATIONS,
    "plan-project": ADD_ANNOTATIONS,
    "modify-task": UPDATE_ANNOTATIONS,
    # === GTD Reflect Tools ===
    "daily-review": READ_ONLY_ANNOTATIONS,
    "weekly-review": READ_ONLY_ANNOTATIONS,
    # === Utility Tools ===
    "search-tasks": READ_ONLY_ANNOTATIONS,
    "get-projects": READ_ONLY_ANNOTATIONS,
    "get-areas": READ_ONLY_ANNOTATIONS,
    "get-tags": READ_ONLY_ANNOTATIONS,
    "show-in-app": READ_ONLY_ANNOTATIONS,
    "get-cache-stats": READ_ONLY_ANNOTATIONS,
    # === Deprecated Tools (aliases for backward compatibility) ===
    "get-inbox": READ_ONLY_ANNOTATIONS,
    "get-today": READ_ONLY_ANNOTATIONS,
    "get-upcoming": READ_ONLY_ANNOTATIONS,
    "get-anytime": READ_ONLY_ANNOTATIONS,
    "get-someday": READ_ONLY_ANNOTATIONS,
    "get-logbook": READ_ONLY_ANNOTATIONS,
    "get-trash": READ_ONLY_ANNOTATIONS,
    "get-todos": READ_ONLY_ANNOTATIONS,
    "get-tagged-items": READ_ONLY_ANNOTATIONS,
    "search-todos": READ_ONLY_ANNOTATIONS,
    "search-advanced": READ_ONLY_ANNOTATIONS,
    "add-todo": ADD_ANNOTATIONS,
    "add-project": ADD_ANNOTATIONS,
    "update-todo": UPDATE_ANNOTATIONS,
    "update-project": UPDATE_ANNOTATIONS,
    "show-item": READ_ONLY_ANNOTATIONS,
    "search-items": READ_ONLY_ANNOTATIONS,
    "get-recent": READ_ONLY_ANNOTATIONS,
}
