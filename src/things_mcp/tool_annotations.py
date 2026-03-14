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

DESTRUCTIVE_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
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
    "create-area": ADD_ANNOTATIONS,
    "modify-project": UPDATE_ANNOTATIONS,
    "modify-area": UPDATE_ANNOTATIONS,
    "delete-area": DESTRUCTIVE_ANNOTATIONS,
    "merge-areas": DESTRUCTIVE_ANNOTATIONS,
    # === GTD Reflect Tools ===
    "daily-review": READ_ONLY_ANNOTATIONS,
    "weekly-review": READ_ONLY_ANNOTATIONS,
    # === Utility Tools ===
    "search-tasks": READ_ONLY_ANNOTATIONS,
    "get-projects": READ_ONLY_ANNOTATIONS,
    "get-areas": READ_ONLY_ANNOTATIONS,
    "get-project": READ_ONLY_ANNOTATIONS,
    "get-area": READ_ONLY_ANNOTATIONS,
    "get-tags": READ_ONLY_ANNOTATIONS,
    "show-in-app": READ_ONLY_ANNOTATIONS,
    "get-cache-stats": READ_ONLY_ANNOTATIONS,
    "triage-insights": READ_ONLY_ANNOTATIONS,
}
