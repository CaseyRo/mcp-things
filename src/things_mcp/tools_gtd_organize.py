"""GTD Organize Tools: schedule, delegate, defer, plan, modify.

These tools handle the "Organize" stage of GTD - putting things where they belong.
"""

from typing import Optional, List, Dict, Any

import things
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult

from .models import ToolEnvelope, WriteResult, output_schema_for
from .tool_results import write_result
from .utils import app_state
from .url_scheme import (
    add_todo,
    update_todo,
    update_project,
    execute_url,
    launch_things,
    add_project_with_tasks,
)
from .logging_config import get_logger
from .cache import invalidate_caches_for
from .tag_handler import ensure_tags_exist
from .tool_annotations import TOOL_ANNOTATIONS, tags_for
from .applescript_bridge import run_applescript, escape_applescript_string
from .triage_tracker import triage_tracker
from .input_validation import validate_tag_names, validate_name, validate_notes_length
from .resolvers import resolve_list_id
from .write_overlay import record_write

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


# Case-insensitive, trimmed tokens that mean "clear this date field" (CDI-1167).
# The empty string is included so a raw "" still clears, but note that the
# documented user-facing way is a NON-empty sentinel (e.g. "none"): some MCP
# clients and middleware drop empty-string optional params before they reach
# the handler, so an empty string is not a reliable clear signal over the wire.
_CLEAR_DATE_SENTINELS = frozenset({"", "none", "clear", "remove", "null"})


def _normalize_clearable_date(value: Optional[str]) -> Optional[str]:
    """Normalize a clearable date field (``when`` / ``deadline``) for updates.

    Maps any clear-sentinel (case-insensitive, whitespace-trimmed) to the empty
    string ``""``. The URL scheme emits ``""`` as ``key=`` which Things treats
    as "clear this field". Real dates and ``None`` (meaning "not provided, leave
    unchanged") pass through untouched.

    Args:
        value: The raw ``when``/``deadline`` argument, or ``None``.

    Returns:
        ``None`` if not provided, ``""`` to clear, otherwise the original value.
    """
    if value is None:
        return None
    if value.strip().lower() in _CLEAR_DATE_SENTINELS:
        return ""
    return value


def _resolve_task_by_title(task_title: str) -> str:
    """Resolve a task_title to a UUID. Returns UUID or raises ToolError.

    Reads through the overlay-aware ``reader`` (CDI-1255) so a task captured a
    moment ago is matchable even before Things flushes it to SQLite. A
    provisional overlay match has only a synthetic ``overlay:`` id (the write
    path never returns a real UUID), so it cannot be mutated by id — we surface a
    staleness-aware error telling the caller to retry shortly rather than a flat
    false "No task found".
    """
    from . import reader as db

    matches = db.todos(status="incomplete")
    matches = [t for t in matches if task_title.lower() in t.get("title", "").lower()]

    # An overlay-only match means the item exists but isn't yet persisted, so we
    # have no real UUID to act on. Treat it as "stale index", not "not found".
    real_matches = [
        m for m in matches if not str(m.get("uuid", "")).startswith("overlay:")
    ]

    if len(matches) >= 1 and len(real_matches) == 0:
        _error_result(
            f"'{task_title}' was just captured but Things has not flushed it to "
            "the read index yet, so it has no addressable id. Wait a moment and "
            "retry, or pass task_id directly."
        )
    matches = real_matches
    if len(matches) == 0:
        stale = db.index_stale()
        if stale:
            _error_result(
                f"No task found matching '{task_title}' yet — a task was captured "
                "very recently and may not be in the read index. Retry shortly, "
                "or pass task_id directly."
            )
        _error_result(
            f"No task found matching '{task_title}'.\n"
            "Use search-tasks to find the correct task."
        )
    if len(matches) > 1:
        result = (
            f"Found {len(matches)} tasks matching '{task_title}'. Please specify:\n\n"
        )
        for t in matches[:5]:
            result += f"- **{t.get('title')}** (ID: `{t.get('uuid')}`)\n"
        if len(matches) > 5:
            result += f"\n...and {len(matches) - 5} more."
        _error_result(result)
    return matches[0].get("uuid")


def register_gtd_organize_tools(mcp: FastMCP):
    """Register GTD Organize stage tools with the MCP server."""

    @mcp.tool(
        name="schedule-task",
        annotations=TOOL_ANNOTATIONS["schedule-task"],
        tags=tags_for("schedule-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def schedule_task(
        title: str,
        when: str,
        deadline: Optional[str] = None,
        project: Optional[str] = None,
        area: Optional[str] = None,
        context: Optional[List[str]] = None,
        checklist: Optional[List[str]] = None,
        notes: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Create a task with specific scheduling and organization.

        GTD Stage: Organize
        Use when: You know when/where this task belongs.
        Instead use: capture-task for quick capture without organizing.

        Args:
            title: What needs to be done
            when: Schedule - today, tomorrow, evening, anytime, someday, or YYYY-MM-DD
            deadline: Hard deadline (YYYY-MM-DD)
            project: Project name or UUID to add to
            area: Area name or UUID
            context: GTD context tags (e.g., ["@computer", "high-energy"])
            checklist: Subtasks/checklist items
            notes: Additional notes
        """
        if ctx:
            await ctx.info(f"Scheduling task for {when}...")

        try:
            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Combine context with any other tags
            tags = context if context else None
            if tags:
                ensure_tags_exist(tags)

            # Resolve project or area to list_id/list_title
            list_id = None
            list_title = project  # project name passed directly
            if area:
                list_id = resolve_list_id(area, "area")
                list_title = None  # area uses list_id, not list_title

            # Build URL
            url = add_todo(
                title=title,
                notes=notes,
                when=when,
                deadline=deadline,
                tags=tags,
                checklist_items=checklist,
                list_id=list_id,
                list_title=list_title,
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to schedule task")

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-upcoming", "get-anytime"]
            )

            # Record in the write overlay for read-your-writes consistency
            # (CDI-1255): a scheduled task is a brand-new item the read index may
            # not have flushed yet.
            record_write(title, when=when, tags=tags, notes=notes)

            text_body = f"Scheduled: {title}\n"
            text_body += f"- When: {when}\n"
            if deadline:
                text_body += f"- Deadline: {deadline}\n"
            if project:
                text_body += f"- Project: {project}\n"
            if context:
                text_body += f"- Context: {', '.join(context)}\n"

            return write_result(
                summary=f"Scheduled: {title} ({when})",
                thing_id=None,
                acknowledged=True,
                text=text_body,
                meta={
                    "when": when,
                    "deadline": deadline,
                    "project": project,
                    "area": area,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error scheduling task", exc_info=True)
            _error_result("Failed to schedule task. Check server logs for details.")

    @mcp.tool(
        name="delegate-task",
        annotations=TOOL_ANNOTATIONS["delegate-task"],
        tags=tags_for("delegate-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def delegate_task(
        task_id: Optional[str] = None,
        task_title: Optional[str] = None,
        delegated_to: str = "",
        follow_up_date: Optional[str] = None,
        notes: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Delegate a task and track it as 'Waiting For'.

        GTD Stage: Organize
        Use when: You've handed off a task to someone else.

        This adds a 'waiting-for' tag, updates the title to show who you're
        waiting on, and sets an optional follow-up deadline.

        Args:
            task_id: UUID of the task to delegate (preferred if known)
            task_title: Title to search for (fuzzy match). If multiple match, returns list.
            delegated_to: Person's name you're waiting on (required)
            follow_up_date: When to follow up (YYYY-MM-DD)
            notes: Notes about the delegation (e.g., "Emailed on Jan 20")
        """
        if not delegated_to:
            _error_result("delegated_to is required — who are you handing this off to?")

        if ctx:
            await ctx.info(f"Delegating task to {delegated_to}...")

        if not task_id and not task_title:
            _error_result("Provide either task_id or task_title to identify the task.")

        try:
            if task_title and not task_id:
                task_id = _resolve_task_by_title(task_title)

            # Get the original task
            task = things.get(task_id)
            if not task:
                _error_result(f"Task not found: {task_id}")

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            original_title = task.get("title", "")
            new_title = f"Waiting: {delegated_to} - {original_title}"

            # Build delegation note
            from datetime import date

            delegation_note = f"\n[Delegated {date.today().isoformat()}]"
            if notes:
                delegation_note += f" {notes}"

            # Ensure waiting-for tag exists
            ensure_tags_exist(["waiting-for"])

            # Update the task
            url = update_todo(
                id=task_id,
                title=new_title,
                append_notes=delegation_note,
                add_tags=["waiting-for"],
                deadline=follow_up_date,
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to delegate task")

            invalidate_caches_for(["get-tasks"])

            # Track triage action
            try:
                triage_tracker.record(
                    task_id=task_id,
                    task_title=task.get("title", ""),
                    task_notes=task.get("notes"),
                    task_tags=task.get("tags"),
                    action="delegated",
                    action_details={"delegated_to": delegated_to},
                )
            except Exception:
                logger.debug("Triage tracking failed (non-critical)")

            text_body = f"Delegated to {delegated_to}: {original_title}\n"
            text_body += "- Tagged: waiting-for\n"
            if follow_up_date:
                text_body += f"- Follow up: {follow_up_date}\n"
            else:
                text_body += "- No follow-up date set. Will appear in weekly review.\n"

            return write_result(
                summary=f"Delegated to {delegated_to}: {original_title}",
                thing_id=task_id,
                acknowledged=True,
                text=text_body,
                meta={
                    "delegated_to": delegated_to,
                    "follow_up_date": follow_up_date,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error delegating task", exc_info=True)
            _error_result("Failed to delegate task. Check server logs for details.")

    @mcp.tool(
        name="defer-task",
        annotations=TOOL_ANNOTATIONS["defer-task"],
        tags=tags_for("defer-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def defer_task(
        task_id: Optional[str] = None,
        task_title: Optional[str] = None,
        defer_to: str = "",
        reason: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Defer a task to a later time.

        GTD Stage: Organize

        IMPORTANT - GTD distinguishes two types of deferral:
        - defer_to="someday" -> Someday/Maybe list (indefinite incubation)
        - defer_to=date -> Tickler file (will reappear on that date)

        Args:
            task_id: UUID of the task to defer (preferred if known)
            task_title: Title to search for (fuzzy match). If multiple match, returns list.
            defer_to: When - "someday", "tomorrow", "next_week", or YYYY-MM-DD (required)
            reason: Why you're deferring (appended to notes)
        """
        if not defer_to:
            _error_result("defer_to is required — when should this task reappear?")

        if ctx:
            await ctx.info(f"Deferring task to {defer_to}...")

        if not task_id and not task_title:
            _error_result("Provide either task_id or task_title to identify the task.")

        try:
            if task_title and not task_id:
                task_id = _resolve_task_by_title(task_title)

            # Fetch task data before update (needed for categorization)
            task_data = things.get(task_id) or {}

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Map friendly names to Things values
            when_map = {
                "someday": "someday",
                "tomorrow": "tomorrow",
                "next_week": None,  # Calculate date
            }

            when_value = when_map.get(defer_to, defer_to)

            # Handle next_week specially
            if defer_to == "next_week":
                from datetime import date, timedelta

                next_monday = date.today() + timedelta(
                    days=(7 - date.today().weekday())
                )
                when_value = next_monday.isoformat()

            # Build notes update
            notes_update = None
            if reason:
                from datetime import date

                notes_update = f"\n[Deferred {date.today().isoformat()}] {reason}"

            # Update the task
            url = update_todo(
                id=task_id,
                when=when_value,
                append_notes=notes_update,
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to defer task")

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-upcoming", "get-someday"]
            )

            # Track triage action
            try:
                action = (
                    "deferred-someday" if defer_to == "someday" else "deferred-date"
                )
                triage_tracker.record(
                    task_id=task_id,
                    task_title=task_data.get("title", ""),
                    task_notes=task_data.get("notes"),
                    task_tags=task_data.get("tags"),
                    action=action,
                    action_details={"defer_to": defer_to},
                )
            except Exception:
                logger.debug("Triage tracking failed (non-critical)")

            if defer_to == "someday":
                text_body = (
                    "Moved to Someday/Maybe for incubation.\n\n"
                    "This item will appear in your weekly review for reconsideration."
                )
                summary = "Moved to Someday/Maybe."
            else:
                text_body = (
                    f"Deferred to {when_value}. Task will reappear on that date."
                )
                summary = f"Deferred to {when_value}."

            return write_result(
                summary=summary,
                thing_id=task_id,
                acknowledged=True,
                text=text_body,
                meta={"defer_to": defer_to, "when": when_value},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error deferring task", exc_info=True)
            _error_result("Failed to defer task. Check server logs for details.")

    @mcp.tool(
        name="plan-project",
        annotations=TOOL_ANNOTATIONS["plan-project"],
        tags=tags_for("plan-project"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def plan_project(
        title: str,
        tasks: List[Dict[str, Any]],
        notes: Optional[str] = None,
        when: Optional[str] = None,
        deadline: Optional[str] = None,
        area: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Create a project with initial tasks atomically.

        GTD Stage: Organize
        Use when: Planning a multi-step outcome.
        GTD rule: Always include at least one next action (when='anytime').

        Args:
            title: Project title
            tasks: List of task objects - each with 'title' and optional 'when', 'notes', 'tags'
            notes: Project notes
            when: Project schedule
            deadline: Project deadline
            area: Area name to add to

        Example tasks:
            [
                {"title": "Research options", "when": "anytime"},
                {"title": "Draft proposal", "when": "anytime"},
                {"title": "Review with team"}
            ]
        """
        if ctx:
            await ctx.info(f"Creating project: {title}...")

        try:
            # Validate inputs
            validate_name(title, "title")
            if notes:
                validate_notes_length(notes)

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Check for next action
            has_next_action = any(
                t.get("when") in ("anytime", "today", None) for t in tasks
            )

            # Use JSON API for atomic creation
            url = add_project_with_tasks(
                title=title,
                tasks=tasks,
                notes=notes,
                when=when,
                deadline=deadline,
                area=area,
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to create project")

            invalidate_caches_for(["get-projects", "get-tasks"])

            text_body = f"Created project: {title}\n"
            text_body += f"- {len(tasks)} tasks added\n"
            if deadline:
                text_body += f"- Deadline: {deadline}\n"

            if not has_next_action:
                text_body += (
                    "\n**Warning:** No immediate next action. GTD recommends at "
                    "least one task with when='anytime' to make progress."
                )

            return write_result(
                summary=f"Created project: {title}",
                thing_id=None,
                acknowledged=True,
                text=text_body,
                meta={
                    "task_count": len(tasks),
                    "has_next_action": has_next_action,
                    "deadline": deadline,
                    "area": area,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error creating project", exc_info=True)
            _error_result("Failed to create project. Check server logs for details.")

    @mcp.tool(
        name="modify-task",
        annotations=TOOL_ANNOTATIONS["modify-task"],
        tags=tags_for("modify-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def modify_task(
        task_id: Optional[str] = None,
        task_title: Optional[str] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        add_notes: Optional[str] = None,
        when: Optional[str] = None,
        deadline: Optional[str] = None,
        tags: Optional[List[str]] = None,
        add_tags: Optional[List[str]] = None,
        checklist: Optional[List[str]] = None,
        add_checklist: Optional[List[str]] = None,
        project: Optional[str] = None,
        area: Optional[str] = None,
        canceled: Optional[bool] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] General task modification for updates not covered by specific tools.

        GTD Stage: Organize
        Instead use: complete-task for completing, defer-task for rescheduling,
                     delegate-task for delegation.

        Clearing a deadline or schedule (CDI-1167):
            To CLEAR an existing deadline or start date, pass one of the
            clear-sentinels as the value (case-insensitive): "none", "clear",
            "remove", or "null". An empty string also clears, but a non-empty
            sentinel is the reliable contract because some clients/middleware
            drop empty optional params before they reach the server.
            Leave a field as null (omit it) to keep it unchanged.

            Common case — move an overdue task to Someday AND drop the stale
            deadline so it stops showing overdue, in a single call:

                modify-task(task_id=..., when="someday", deadline="none")

        Args:
            task_id: UUID of the task to update (preferred if known)
            task_title: Title to search for (fuzzy match). If multiple match, returns list.
            title: New title (replaces existing)
            notes: New notes (replaces existing)
            add_notes: Notes to append (preserves existing)
            when: New schedule (today, tomorrow, evening, anytime, someday,
                YYYY-MM-DD). Pass "none"/"clear"/"remove"/"null" to clear it.
            deadline: New deadline (YYYY-MM-DD). Pass "none"/"clear"/"remove"/
                "null" to clear an existing deadline.
            tags: New tags (replaces existing)
            add_tags: Tags to add (preserves existing)
            checklist: New checklist items (replaces existing)
            add_checklist: Checklist items to append (preserves existing)
            project: Project name or UUID to move task to
            area: Area name or UUID to move task to
            canceled: Set to true to trash/cancel the task
        """
        if not task_id and not task_title:
            _error_result("Provide either task_id or task_title to identify the task.")

        if ctx:
            await ctx.info("Updating task...")

        # Normalize clearable date fields: map clear-sentinels to "" so the
        # URL scheme emits `when=`/`deadline=` (Things clears the field).
        # CDI-1167: enables clearing a stale deadline / start date.
        when = _normalize_clearable_date(when)
        deadline = _normalize_clearable_date(deadline)

        try:
            if task_title and not task_id:
                task_id = _resolve_task_by_title(task_title)

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Ensure tags exist
            all_tags = (tags or []) + (add_tags or [])
            if all_tags:
                ensure_tags_exist(all_tags)

            # Resolve project/area name to UUID if needed
            list_id = None
            if project:
                list_id = resolve_list_id(project, "project")
            elif area:
                list_id = resolve_list_id(area, "area")

            # Build URL
            url = update_todo(
                id=task_id,
                title=title,
                notes=notes,
                append_notes=add_notes,
                when=when,
                deadline=deadline,
                tags=tags,
                add_tags=add_tags,
                checklist_items=checklist,
                append_checklist_items=add_checklist,
                list_id=list_id,
                canceled=canceled,
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to update task")

            invalidate_caches_for(["get-tasks", "get-projects", "get-inbox"])

            # Track triage action
            try:
                task_data = things.get(task_id) or {}
                action = "canceled" if canceled else "modified"
                triage_tracker.record(
                    task_id=task_id,
                    task_title=task_data.get("title", ""),
                    task_notes=task_data.get("notes"),
                    task_tags=task_data.get("tags"),
                    action=action,
                    action_details={
                        k: v
                        for k, v in {
                            "moved_to_project": project,
                            "moved_to_area": area,
                            "scheduled": when,
                        }.items()
                        if v
                    },
                )
            except Exception:
                logger.debug("Triage tracking failed (non-critical)")

            text_body = "Task updated successfully."
            if canceled:
                text_body = "Task canceled."
            elif project:
                text_body += f" Moved to project: {project}"
            elif area:
                text_body += f" Moved to area: {area}"

            return write_result(
                summary="Task canceled." if canceled else "Task updated.",
                thing_id=task_id,
                acknowledged=True,
                text=text_body,
                meta={
                    "canceled": bool(canceled),
                    "moved_to_project": project,
                    "moved_to_area": area,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error updating task", exc_info=True)
            _error_result("Failed to update task. Check server logs for details.")

    @mcp.tool(
        name="create-area",
        annotations=TOOL_ANNOTATIONS["create-area"],
        tags=tags_for("create-area"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def create_area(
        name: str,
        tags: Optional[List[str]] = None,
        projects: Optional[List[str]] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Create a new area in Things, optionally with initial projects.

        GTD Stage: Organize
        Use when: Setting up a new area of responsibility (e.g., Health, Finance, Work).
        Areas are not created via the URL scheme — this uses AppleScript.

        Args:
            name: Area name (e.g., "Health", "Side Projects")
            tags: Optional tags to assign to the area
            projects: Optional list of project names to create within the area
        """
        if ctx:
            await ctx.info(f"Creating area: {name}...")

        try:
            validate_name(name, "name")
            if projects:
                for p_name in projects:
                    validate_name(p_name, "project name")

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Check if area already exists
            existing_areas = things.areas()
            if any(
                a.get("title", "").lower() == name.lower()
                for a in (existing_areas or [])
            ):
                _error_result(f"Area already exists: {name}")

            # Build AppleScript to create the area
            escaped_name = escape_applescript_string(name)
            if tags:
                validate_tag_names(tags)
                ensure_tags_exist(tags)
                # Use proper AppleScript list construction to prevent injection
                tag_list = (
                    "{"
                    + ", ".join(f'"{escape_applescript_string(t)}"' for t in tags)
                    + "}"
                )
                script = (
                    f'tell application "Things3"\n'
                    f"  make new area with properties "
                    f'{{name:"{escaped_name}", tag names:{tag_list}}}\n'
                    f"end tell"
                )
            else:
                script = (
                    f'tell application "Things3"\n'
                    f'  make new area with properties {{name:"{escaped_name}"}}\n'
                    f"end tell"
                )

            result = run_applescript(script)

            if result is False:
                _error_result(f"Failed to create area: {name}")

            invalidate_caches_for(["get-areas"])

            # Create initial projects if requested
            created_projects = []
            if projects:
                for p_name in projects:
                    p_url = add_project_with_tasks(title=p_name, tasks=[], area=name)
                    if execute_url(p_url):
                        created_projects.append(p_name)
                invalidate_caches_for(["get-projects"])

            text_body = f"Created area: {name}"
            if created_projects:
                text_body += (
                    f"\nCreated {len(created_projects)} project(s): "
                    f"{', '.join(created_projects)}"
                )
                text_body += (
                    "\n\nThese projects have no tasks yet — they will appear as "
                    "stalled in weekly review until you add next actions "
                    "(GTD: every project needs a next action)."
                )
            return write_result(
                summary=f"Created area: {name}",
                thing_id=None,
                acknowledged=True,
                text=text_body,
                meta={
                    "name": name,
                    "tags": tags or [],
                    "projects_created": created_projects,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error creating area", exc_info=True)
            _error_result("Failed to create area. Check server logs for details.")

    # === Project/Area CRUD Tools ===

    @mcp.tool(
        name="modify-project",
        annotations=TOOL_ANNOTATIONS["modify-project"],
        tags=tags_for("modify-project"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def modify_project(
        name_or_uuid: str,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        prepend_notes: Optional[str] = None,
        append_notes: Optional[str] = None,
        when: Optional[str] = None,
        deadline: Optional[str] = None,
        tags: Optional[List[str]] = None,
        add_tags: Optional[List[str]] = None,
        area: Optional[str] = None,
        completed: Optional[bool] = None,
        canceled: Optional[bool] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Update a project's properties.

        Use when: Renaming, rescheduling, reassigning to an area, adding notes,
        or closing a project.

        Things 3 notes: `completed` and `canceled` are Things 3 features.
        In GTD, a project you finish is simply removed from the active list.
        A project you decide not to pursue goes to Someday/Maybe or is removed.

        Args:
            name_or_uuid: Project name (case-insensitive) or UUID
            title: New title
            notes: New notes (replaces existing)
            prepend_notes: Text to add before existing notes
            append_notes: Text to add after existing notes
            when: Schedule date (today, tomorrow, evening, anytime, someday, YYYY-MM-DD)
            deadline: Deadline date (YYYY-MM-DD)
            tags: Tags to set (replaces existing)
            add_tags: Tags to add without replacing
            area: Area name or UUID to move project to
            completed: Mark as completed (Things 3 feature)
            canceled: Mark as canceled (Things 3 feature)
        """
        if ctx:
            await ctx.info("Modifying project...")

        try:
            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Resolve project name to UUID
            project_uuid = resolve_list_id(name_or_uuid, "project")

            # Validate inputs
            if title:
                validate_name(title, "title")
            if notes:
                validate_notes_length(notes)
            if prepend_notes:
                validate_notes_length(prepend_notes)
            if append_notes:
                validate_notes_length(append_notes)
            if tags:
                validate_tag_names(tags)
                ensure_tags_exist(tags)
            if add_tags:
                validate_tag_names(add_tags)
                ensure_tags_exist(add_tags)

            # Resolve area name to UUID if provided
            area_id = None
            if area:
                area_id = resolve_list_id(area, "area")

            # Check for incomplete tasks if completing
            completion_note = ""
            if completed:
                incomplete = things.todos(project=project_uuid, status="incomplete")
                if incomplete:
                    completion_note = (
                        f"\nNote: this project had {len(incomplete)} incomplete "
                        "tasks which are now also completed."
                    )

            # Build and execute URL
            url = update_project(
                id=project_uuid,
                title=title,
                notes=notes,
                prepend_notes=prepend_notes,
                append_notes=append_notes,
                when=when,
                deadline=deadline,
                tags=tags,
                add_tags=add_tags,
                area_id=area_id,
                completed=completed,
                canceled=canceled,
            )
            if not execute_url(url):
                _error_result("Failed to modify project")

            invalidate_caches_for(["get-projects", "get-tasks", "get-areas"])

            # Build result message
            changes = []
            if title:
                changes.append("title updated")
            if notes or prepend_notes or append_notes:
                changes.append("notes updated")
            if when:
                changes.append(f"scheduled: {when}")
            if deadline:
                changes.append(f"deadline: {deadline}")
            if tags or add_tags:
                changes.append("tags updated")
            if area:
                changes.append(f"moved to area: {area}")
            if completed:
                changes.append("marked completed")
            if canceled:
                changes.append("marked canceled")

            text_body = f"Modified project. Changes: {', '.join(changes)}."
            text_body += completion_note

            return write_result(
                summary=f"Modified project: {', '.join(changes)}",
                thing_id=project_uuid,
                acknowledged=True,
                text=text_body,
                meta={"changes": changes},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error modifying project", exc_info=True)
            _error_result("Failed to modify project. Check server logs for details.")

    @mcp.tool(
        name="modify-area",
        annotations=TOOL_ANNOTATIONS["modify-area"],
        tags=tags_for("modify-area"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def modify_area(
        name_or_uuid: str,
        new_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Rename an area or update its tags.

        Use when: Renaming an area of focus/responsibility or changing its tags.

        Args:
            name_or_uuid: Current area name (case-insensitive) or UUID
            new_name: New name for the area
            tags: Tags to set on the area
        """
        if ctx:
            await ctx.info("Modifying area...")

        try:
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Resolve to UUID first (never use user name as AppleScript lookup)
            area_uuid = resolve_list_id(name_or_uuid, "area")

            if not new_name and not tags:
                _error_result("Provide at least one change: new_name or tags")

            # Validate new name
            if new_name:
                validate_name(new_name, "new_name")
                # Check for duplicate
                existing_areas = things.areas()
                if any(
                    a.get("title", "").lower() == new_name.lower()
                    and a.get("uuid") != area_uuid
                    for a in (existing_areas or [])
                ):
                    _error_result(f"Area name already taken: {new_name}")

            # Build AppleScript using UUID lookup (safe from injection)
            script_parts = [
                'tell application "Things3"',
                f'  set targetArea to first area whose id is "{area_uuid}"',
            ]

            if new_name:
                escaped_name = escape_applescript_string(new_name)
                script_parts.append(f'  set name of targetArea to "{escaped_name}"')

            if tags:
                validate_tag_names(tags)
                ensure_tags_exist(tags)
                tag_list = (
                    "{"
                    + ", ".join(f'"{escape_applescript_string(t)}"' for t in tags)
                    + "}"
                )
                script_parts.append(f"  set tag names of targetArea to {tag_list}")

            script_parts.append("end tell")
            script = "\n".join(script_parts)

            result = run_applescript(script)
            if result is False:
                _error_result("Failed to modify area")

            invalidate_caches_for(["get-areas", "get-projects", "get-tasks"])

            changes = []
            if new_name:
                changes.append(f"renamed to '{new_name}'")
            if tags:
                changes.append(f"tags: {', '.join(tags)}")

            text_body = f"Modified area. Changes: {', '.join(changes)}."
            return write_result(
                summary=f"Modified area: {', '.join(changes)}",
                thing_id=area_uuid,
                acknowledged=True,
                text=text_body,
                meta={"changes": changes},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error modifying area", exc_info=True)
            _error_result("Failed to modify area. Check server logs for details.")

    @mcp.tool(
        name="delete-area",
        annotations=TOOL_ANNOTATIONS["delete-area"],
        tags=tags_for("delete-area"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def delete_area(
        name_or_uuid: str,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Delete an area. Refuses if loose to-dos exist (Things trashes them).

        Use when: Removing an area of responsibility that is no longer relevant.
        Projects in the area will become unassigned (safe). Loose to-dos would be
        trashed by Things, so they must be moved first.

        If blocked, use merge-areas to safely move everything to another area first.

        Args:
            name_or_uuid: Area name (case-insensitive) or UUID
        """
        if ctx:
            await ctx.info("Checking area contents...")

        try:
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            area_uuid = resolve_list_id(name_or_uuid, "area")

            # Dry-run: scan contents
            projects = [
                p for p in (things.projects() or []) if p.get("area") == area_uuid
            ]
            loose_todos = [
                t for t in (things.todos(area=area_uuid) or []) if not t.get("project")
            ]

            # Block if loose to-dos exist
            if loose_todos:
                todo_list = "\n".join(f"  - {t['title']}" for t in loose_todos[:10])
                if len(loose_todos) > 10:
                    todo_list += f"\n  ... and {len(loose_todos) - 10} more"
                _error_result(
                    f"Cannot delete area: {len(loose_todos)} loose to-do(s) "
                    "would be trashed by Things.\n\n"
                    f"{todo_list}\n\n"
                    "**Recommended:** Use `merge-areas` to move everything "
                    "to another area first, then delete.\n"
                    "Alternatives: move to-dos into a project, complete them, "
                    "or cancel them."
                )

            # Report projects that will become unassigned
            warning = ""
            if projects:
                proj_list = ", ".join(p["title"] for p in projects[:5])
                if len(projects) > 5:
                    proj_list += f" (+{len(projects) - 5} more)"
                warning = (
                    f"\n{len(projects)} project(s) are now unassigned: "
                    f"{proj_list}. Use `modify-project(area=...)` to reassign."
                )

            # TOCTOU guard: re-check immediately before deletion
            recheck_todos = [
                t for t in (things.todos(area=area_uuid) or []) if not t.get("project")
            ]
            if recheck_todos:
                _error_result(
                    "New to-dos appeared in this area since the check. "
                    "Aborting to prevent data loss. Please retry."
                )

            # Delete via AppleScript using UUID
            script = (
                f'tell application "Things3"\n'
                f'  delete (first area whose id is "{area_uuid}")\n'
                f"end tell"
            )
            result = run_applescript(script)
            if result is False:
                _error_result("Failed to delete area")

            invalidate_caches_for(["get-areas", "get-projects", "get-tasks"])

            text_body = f"Deleted area.{warning}"
            return write_result(
                summary="Deleted area.",
                thing_id=area_uuid,
                acknowledged=True,
                text=text_body,
                meta={
                    "unassigned_project_count": len(projects),
                    "unassigned_project_titles": [p["title"] for p in projects],
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error deleting area", exc_info=True)
            _error_result("Failed to delete area. Check server logs for details.")

    @mcp.tool(
        name="merge-areas",
        annotations=TOOL_ANNOTATIONS["merge-areas"],
        tags=tags_for("merge-areas"),
        timeout=60,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def merge_areas(
        source: str,
        target: str,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Move all contents from source area to target area, then delete source.

        Use when: Two areas of responsibility are converging (e.g., merging
        "Side Projects" into "Work"). Safely moves all to-dos and projects
        before deleting the source.

        Args:
            source: Source area name or UUID (will be deleted)
            target: Target area name or UUID (will receive all items)
        """
        if ctx:
            await ctx.info("Preparing area merge...")

        try:
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Resolve both to UUIDs
            source_uuid = resolve_list_id(source, "area")
            target_uuid = resolve_list_id(target, "area")

            # Self-merge guard (compare UUIDs, not input strings)
            if source_uuid == target_uuid:
                _error_result("Source and target areas are the same")

            # Scan source contents
            source_projects = [
                p for p in (things.projects() or []) if p.get("area") == source_uuid
            ]
            source_todos = [
                t
                for t in (things.todos(area=source_uuid) or [])
                if not t.get("project")
            ]

            # Move all items in a single AppleScript block (O(1) subprocess calls)
            todo_uuids = [t["uuid"] for t in source_todos]
            project_uuids = [p["uuid"] for p in source_projects]

            if todo_uuids or project_uuids:
                # Build a single AppleScript that moves all items
                lines = ['tell application "Things3"']
                lines.append(
                    f'  set targetArea to first area whose id is "{target_uuid}"'
                )

                for uuid in todo_uuids:
                    lines.append(
                        f'  move (first to do whose id is "{uuid}") to targetArea'
                    )

                for uuid in project_uuids:
                    lines.append(
                        f'  move (first project whose id is "{uuid}") to targetArea'
                    )

                lines.append("end tell")
                script = "\n".join(lines)

                result = run_applescript(script)
                if result is False:
                    _error_result(
                        f"Batch move failed. "
                        f"Items in source: {len(todo_uuids)} to-do(s), "
                        f"{len(project_uuids)} project(s). "
                        "Re-running merge-areas is safe — already-moved items "
                        "are in the target."
                    )

            # Re-read source to confirm empty before deletion
            remaining_todos = [
                t
                for t in (things.todos(area=source_uuid) or [])
                if not t.get("project")
            ]
            remaining_projects = [
                p for p in (things.projects() or []) if p.get("area") == source_uuid
            ]
            if remaining_todos or remaining_projects:
                _error_result(
                    "Source area is not empty after moves. "
                    f"Remaining: {len(remaining_todos)} to-do(s), "
                    f"{len(remaining_projects)} project(s). "
                    "Not deleting source. Re-run merge-areas to retry."
                )

            # Delete empty source area
            script = (
                f'tell application "Things3"\n'
                f'  delete (first area whose id is "{source_uuid}")\n'
                f"end tell"
            )
            result = run_applescript(script)
            if result is False:
                _error_result(
                    "All items moved successfully but failed to delete source area. "
                    "Delete it manually or retry."
                )

            invalidate_caches_for(["get-areas", "get-projects", "get-tasks"])

            text_body = (
                f"Merged areas. Moved {len(todo_uuids)} to-do(s) and "
                f"{len(project_uuids)} project(s) to target. "
                "Source area deleted."
            )
            return write_result(
                summary=(
                    f"Merged: {len(todo_uuids)} to-do(s) and "
                    f"{len(project_uuids)} project(s) moved; source deleted."
                ),
                thing_id=target_uuid,
                acknowledged=True,
                text=text_body,
                meta={
                    "todos_moved": len(todo_uuids),
                    "projects_moved": len(project_uuids),
                    "source_uuid": source_uuid,
                    "target_uuid": target_uuid,
                },
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error merging areas", exc_info=True)
            _error_result("Failed to merge areas. Check server logs for details.")
