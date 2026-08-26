"""Output formatting for Things 3 domain rows.

Each formatter has two flavours:

- ``to_dict_*``: returns a JSON-friendly dict aligned with the Pydantic models
  in ``models.py``. Used to populate ``ToolEnvelope.data`` for the structured
  response.
- ``render_*``: returns the human-readable string today's tools emit. Used as
  the ``TextContent`` body inside ``ToolResult`` so text-only clients see the
  same prose as before.
"""

from __future__ import annotations

import logging
from typing import Any

import things

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_title(uuid: str | None) -> str | None:
    """Look up an item's title via things-py; swallow lookup failures."""
    if not uuid:
        return None
    try:
        item = things.get(uuid)
        if item:
            return item.get("title")
    except Exception:
        pass
    return None


def _normalise_checklist(raw: Any) -> list[dict[str, Any]]:
    """Coerce a raw checklist into the shape expected by the Pydantic model."""
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        status = entry.get("status", "open")
        if status not in ("open", "completed"):
            status = "completed" if status == "completed" else "open"
        items.append(
            {
                "title": entry.get("title", ""),
                "status": status,
                "uuid": entry.get("uuid"),
            }
        )
    return items


# ---------------------------------------------------------------------------
# Todo
# ---------------------------------------------------------------------------


def to_dict_todo(todo: dict[str, Any]) -> dict[str, Any]:
    """Project a things-py todo row into the canonical Todo shape.

    Always populates `tags` (default []) and `checklist` (default []) so
    consumers can rely on the field being present rather than having to
    distinguish "missing" from "empty".
    """
    project_uuid = todo.get("project")
    project_title = todo.get("project_title") or _resolve_title(project_uuid)
    area_uuid = todo.get("area")
    area_title = todo.get("area_title") or _resolve_title(area_uuid)

    # Normalise status. Real things-py returns incomplete|completed|canceled,
    # but legacy AppleScript-style mocks/fixtures use "open"; coerce so the
    # pydantic Todo model still validates.
    raw_status = todo.get("status")
    if raw_status in (None, "", "open"):
        status = "incomplete"
    elif raw_status in ("incomplete", "completed", "canceled"):
        status = raw_status
    else:
        status = "incomplete"

    start = todo.get("start") or None
    list_label = project_title or area_title or start or "Inbox"

    return {
        "uuid": todo.get("uuid", ""),
        "title": todo.get("title", ""),
        "type": todo.get("type", "to-do"),
        "status": status,
        "notes": todo.get("notes") or None,
        "tags": list(todo.get("tags") or []),
        "checklist": _normalise_checklist(todo.get("checklist")),
        "start": start,
        "start_date": todo.get("start_date") or None,
        "reminder_time": todo.get("reminder_time") or None,
        "deadline": todo.get("deadline") or None,
        "stop_date": todo.get("stop_date") or None,
        "created": todo.get("created") or todo.get("creation_date") or None,
        "modified": todo.get("modified") or todo.get("modification_date") or None,
        "project": project_uuid or None,
        "project_title": project_title,
        "area": area_uuid or None,
        "area_title": area_title,
        "list": list_label,
    }


def render_todo(todo: dict[str, Any]) -> str:
    """Render a todo as the legacy human-readable text block.

    The output is byte-identical to the pre-migration ``format_todo`` so
    snapshot tests stay green. Do not change formatting without bumping the
    spec (see ``Requirement: Tools SHALL also emit a backwards-compatible
    TextContent block``).
    """
    logger.debug("Formatting todo uuid=%s", todo.get("uuid", "unknown"))
    todo_text = f"Title: {todo['title']}"

    todo_text += f"\nUUID: {todo['uuid']}"
    todo_text += f"\nType: {todo['type']}"

    if todo.get("status"):
        todo_text += f"\nStatus: {todo['status']}"

    if todo.get("start"):
        todo_text += f"\nList: {todo['start']}"

    if todo.get("created"):
        todo_text += f"\nCreated: {todo['created']}"
    if todo.get("start_date"):
        todo_text += f"\nStart Date: {todo['start_date']}"
    if todo.get("deadline"):
        todo_text += f"\nDeadline: {todo['deadline']}"
    if todo.get("stop_date"):
        todo_text += f"\nCompleted: {todo['stop_date']}"

    if todo.get("notes"):
        todo_text += f"\nNotes: {todo['notes']}"

    if todo.get("project_title"):
        todo_text += f"\nProject: {todo['project_title']}"
    elif todo.get("project"):
        try:
            project = things.get(todo["project"])
            if project:
                todo_text += f"\nProject: {project['title']}"
        except Exception:
            pass

    if todo.get("area_title"):
        todo_text += f"\nArea: {todo['area_title']}"
    elif todo.get("area"):
        try:
            area = things.get(todo["area"])
            if area:
                todo_text += f"\nArea: {area['title']}"
        except Exception:
            pass

    if todo.get("tags"):
        todo_text += f"\nTags: {', '.join(todo['tags'])}"

    if isinstance(todo.get("checklist"), list):
        todo_text += "\nChecklist:"
        for item in todo["checklist"]:
            status = "✓" if item["status"] == "completed" else "□"
            todo_text += f"\n  {status} {item['title']}"

    return todo_text


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


def to_dict_project(
    project: dict[str, Any], include_items: bool = False
) -> dict[str, Any]:
    """Project a things-py project row into the canonical Project shape."""
    area_uuid = project.get("area")
    area_title = project.get("area_title") or _resolve_title(area_uuid)

    tasks: list[dict[str, Any]] = []
    if include_items:
        try:
            todo_rows = things.todos(project=project["uuid"])
            tasks = [to_dict_todo(t) for t in (todo_rows or [])]
        except Exception:
            logger.debug(
                "Failed to fetch tasks for project %s",
                project.get("uuid"),
                exc_info=True,
            )

    return {
        "uuid": project.get("uuid", ""),
        "title": project.get("title", ""),
        "type": "project",
        "status": project.get("status") or "incomplete",
        "notes": project.get("notes") or None,
        "tags": list(project.get("tags") or []),
        "start": project.get("start") or None,
        "start_date": project.get("start_date") or None,
        "reminder_time": project.get("reminder_time") or None,
        "deadline": project.get("deadline") or None,
        "stop_date": project.get("stop_date") or None,
        "created": project.get("created") or project.get("creation_date") or None,
        "modified": project.get("modified") or project.get("modification_date") or None,
        "area": area_uuid or None,
        "area_title": area_title,
        "tasks": tasks,
    }


def render_project(project: dict[str, Any], include_items: bool = False) -> str:
    """Render a project as the legacy text block."""
    project_text = f"Title: {project['title']}\nUUID: {project['uuid']}"

    if project.get("area_title"):
        project_text += f"\nArea: {project['area_title']}"
    elif project.get("area"):
        try:
            area = things.get(project["area"])
            if area:
                project_text += f"\nArea: {area['title']}"
        except Exception:
            pass

    if project.get("notes"):
        project_text += f"\nNotes: {project['notes']}"

    if include_items:
        todos = things.todos(project=project["uuid"])
        if todos:
            project_text += "\n\nTasks:"
            for todo in todos:
                project_text += f"\n- {todo['title']}"

    return project_text


# ---------------------------------------------------------------------------
# Area
# ---------------------------------------------------------------------------


def to_dict_area(area: dict[str, Any], include_items: bool = False) -> dict[str, Any]:
    """Project a things-py area row into the canonical Area shape."""
    projects: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    if include_items:
        try:
            project_rows = things.projects(area=area["uuid"])
            projects = [to_dict_project(p) for p in (project_rows or [])]
        except Exception:
            logger.debug(
                "Failed to fetch projects for area %s", area.get("uuid"), exc_info=True
            )
        try:
            todo_rows = things.todos(area=area["uuid"])
            tasks = [to_dict_todo(t) for t in (todo_rows or []) if not t.get("project")]
        except Exception:
            logger.debug(
                "Failed to fetch todos for area %s", area.get("uuid"), exc_info=True
            )

    return {
        "uuid": area.get("uuid", ""),
        "title": area.get("title", ""),
        "notes": area.get("notes") or None,
        "tags": list(area.get("tags") or []),
        "projects": projects,
        "tasks": tasks,
    }


def render_area(area: dict[str, Any], include_items: bool = False) -> str:
    """Render an area as the legacy text block."""
    area_text = f"Title: {area['title']}\nUUID: {area['uuid']}"

    if area.get("notes"):
        area_text += f"\nNotes: {area['notes']}"

    if include_items:
        projects = things.projects(area=area["uuid"])
        if projects:
            area_text += "\n\nProjects:"
            for project in projects:
                area_text += f"\n- {project['title']}"

        todos = things.todos(area=area["uuid"])
        if todos:
            area_text += "\n\nTasks:"
            for todo in todos:
                area_text += f"\n- {todo['title']}"

    return area_text


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------


def to_dict_tag(tag: dict[str, Any], include_items: bool = False) -> dict[str, Any]:
    """Project a things-py tag row into the canonical Tag shape.

    `include_items` is accepted for symmetry but does not embed items in the
    structured output today; callers that need tagged items should query via
    `db.todos(tag=...)` directly.
    """
    return {
        "uuid": tag.get("uuid", ""),
        "title": tag.get("title", ""),
        "shortcut": tag.get("shortcut") or None,
        "parent": tag.get("parent") or None,
    }


def render_tag(tag: dict[str, Any], include_items: bool = False) -> str:
    """Render a tag as the legacy text block."""
    tag_text = f"Title: {tag['title']}\nUUID: {tag['uuid']}"

    if tag.get("shortcut"):
        tag_text += f"\nShortcut: {tag['shortcut']}"

    if include_items:
        todos = things.todos(tag=tag["title"])
        if todos:
            tag_text += "\n\nTagged Items:"
            for todo in todos:
                tag_text += f"\n- {todo['title']}"

    return tag_text
