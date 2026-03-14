"""Name-to-UUID resolution for Things projects and areas.

Shared by tools_utility.py (read tools) and tools_gtd_organize.py (write tools).
Depends only on `things` (third-party) and `ToolError` (FastMCP) — no tool-module imports.
"""

from typing import List

import things
from fastmcp.exceptions import ToolError


def resolve_list_id(name_or_uuid: str, list_type: str) -> str:
    """Resolve a project/area name or UUID to a UUID.

    Args:
        name_or_uuid: Project/area name or UUID
        list_type: "project" or "area"

    Returns:
        UUID string

    Raises:
        ToolError if not found or ambiguous
    """
    # If it looks like a UUID, try direct lookup first
    item = things.get(name_or_uuid)
    if item:
        return name_or_uuid

    # Search by name
    items = things.projects() if list_type == "project" else things.areas()

    matches = [
        i for i in (items or []) if i.get("title", "").lower() == name_or_uuid.lower()
    ]

    if len(matches) == 1:
        return matches[0]["uuid"]
    elif len(matches) > 1:
        raise ToolError(
            f"Multiple {list_type}s match '{name_or_uuid}'. "
            f"Use UUID instead: {', '.join(m['uuid'] for m in matches)}"
        )
    else:
        raise ToolError(f"{list_type.capitalize()} not found: {name_or_uuid}")


def resolve_item(name_or_uuid: str, item_type: str) -> dict:
    """Resolve a project/area name or UUID to the full item dict.

    For ambiguous matches, returns a disambiguation list formatted as a bulleted
    list with title, UUID, and key details (matching complete-task format).

    Args:
        name_or_uuid: Project/area name or UUID
        item_type: "project" or "area"

    Returns:
        Full item dict from things-py

    Raises:
        ToolError if not found; returns disambiguation string if ambiguous
    """
    # Try direct UUID lookup
    item = things.get(name_or_uuid)
    if item:
        return item

    # Search by name
    items = things.projects() if item_type == "project" else things.areas()

    matches = [
        i for i in (items or []) if i.get("title", "").lower() == name_or_uuid.lower()
    ]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        lines = _format_disambiguation(matches, item_type)
        raise ToolError(
            f"Multiple {item_type}s match '{name_or_uuid}'. "
            f"Specify by UUID:\n" + "\n".join(lines)
        )
    else:
        raise ToolError(f"{item_type.capitalize()} not found: {name_or_uuid}")


def _format_disambiguation(matches: List[dict], item_type: str) -> List[str]:
    """Format a disambiguation list matching complete-task's bulleted format."""
    lines = []
    for m in matches:
        uuid = m.get("uuid", "?")
        title = m.get("title", "Untitled")
        if item_type == "project":
            area = m.get("area_title", "no area")
            status = m.get("status", "unknown")
            lines.append(f"  - {title} ({uuid}) — area: {area}, status: {status}")
        else:
            lines.append(f"  - {title} ({uuid})")
    return lines
