"""GTD Core Tools: Engage, Capture, and Clarify stages.

These tools form the "input" side of GTD:
- Engage: get-tasks, focus-mode, complete-task
- Capture: capture-task
- Clarify: process-inbox, convert-to-project
"""

from typing import Literal, Optional, List, Union

from . import reader as db
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult

from .formatters import render_todo, to_dict_todo
from .models import FocusResult, Todo, ToolEnvelope, WriteResult, output_schema_for
from .tool_results import make_result, write_result
from .utils import app_state
from .url_scheme import (
    add_todo,
    update_todo,
    execute_url,
    launch_things,
    add_project_with_tasks,
)
from .logging_config import get_logger
from .cache import invalidate_caches_for
from .tag_handler import ensure_tags_exist
from .tool_annotations import TOOL_ANNOTATIONS, tags_for
from .triage_tracker import triage_tracker
from .settings import get_dashboard_url
from .write_overlay import record_write

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def register_gtd_core_tools(mcp: FastMCP):
    """Register GTD Engage, Capture, and Clarify tools with the MCP server."""

    # --- GTD ENGAGE STAGE ---

    @mcp.tool(
        name="get-tasks",
        annotations=TOOL_ANNOTATIONS["get-tasks"],
        tags=tags_for("get-tasks"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[list[Todo]]),
    )
    async def get_tasks(
        view: Optional[
            Literal[
                "inbox",
                "today",
                "tomorrow",
                "upcoming",
                "anytime",
                "someday",
                "logbook",
                "trash",
                "deadlines",
            ]
        ] = None,
        context: Optional[Union[str, List[str]]] = None,
        energy: Optional[str] = None,
        time_available: Optional[str] = None,
        area: Optional[str] = None,
        project: Optional[str] = None,
        include_completed: bool = False,
        limit: int = 50,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Get tasks filtered by view, context, energy, and time available.

        GTD Stage: Engage
        Use when: Choosing what to work on based on current context and constraints.

        Context is your FIRST filter in GTD. Common contexts:
        - @computer, @phone, @office, @home, @errands, @anywhere

        Returns a ``ToolResult`` whose ``structured_content`` is a
        ``ToolEnvelope[list[Todo]]`` payload (see ``models.py``):

        - ``data``: list of Todo objects with full Things 3 metadata —
          ``uuid``, ``title``, ``type``, ``status``, ``notes``, ``tags``,
          ``start``, ``start_date``, ``deadline``, ``stop_date``, ``created``,
          ``modified``, ``project``, ``project_title``, ``area``,
          ``area_title``. Checklists are not enriched in list view.
        - ``summary``: one-line headline (e.g. ``"3 tasks in today"``).
        - ``meta``: ``total_count`` and ``truncated`` when results are sliced.

        The ``content`` text block preserves the legacy human-readable prose
        for backwards compatibility.

        Args:
            view: Task view - inbox, today, tomorrow, upcoming, anytime, someday, logbook, trash, deadlines
            context: GTD context tag(s) to filter by (e.g., "@computer", "@phone")
            energy: Energy level tag (e.g., "high-energy", "low-energy")
            time_available: Time estimate tag (e.g., "5min", "15min", "30min", "1hr+")
            area: Filter by area name or UUID
            project: Filter by project name or UUID
            include_completed: Include completed tasks (default False)
            limit: Maximum number of tasks to return (default 50, max 200)

        Examples:
            get_tasks(view="today") - What's scheduled for today?
            get_tasks(context="@computer") - What can I do at my desk?
            get_tasks(view="anytime", context="@errands") - What can I do while out?
            get_tasks(context="waiting-for") - What am I waiting on others for?
        """
        if ctx:
            await ctx.info(f"Fetching tasks (view={view}, context={context})...")

        # CDI-1255: built-in lists (Inbox, Today, ...) are not areas. If someone
        # passes a list name as `area`, redirect them to the matching `view`
        # rather than filtering by a non-existent area and returning empty.
        if area and area.strip().lower() in {
            "inbox",
            "today",
            "tomorrow",
            "upcoming",
            "anytime",
            "someday",
            "logbook",
            "trash",
            "deadlines",
        }:
            list_name = area.strip().lower()
            _error_result(
                f"'{area}' is a built-in Things list, not an area. "
                f"Use view='{list_name}' (not area='{area}') to list its contents."
            )

        try:
            # Build query based on view
            if view == "inbox":
                todos = db.inbox()
            elif view == "today":
                todos = db.today()
            elif view == "tomorrow":
                # Things doesn't have a direct tomorrow() function
                todos = db.upcoming()
                # Filter to tomorrow only
                from datetime import date, timedelta

                tomorrow = (date.today() + timedelta(days=1)).isoformat()
                todos = [t for t in todos if t.get("start_date") == tomorrow]
            elif view == "upcoming":
                todos = db.upcoming()
            elif view == "anytime":
                todos = db.anytime()
            elif view == "someday":
                todos = db.someday()
            elif view == "logbook":
                todos = db.logbook()
            elif view == "trash":
                todos = db.trash()
            elif view == "deadlines":
                # Get tasks with deadlines
                todos = db.todos(deadline=True)
            elif view is None:
                # No view specified, get all incomplete tasks
                todos = (
                    db.todos(status="incomplete")
                    if not include_completed
                    else db.todos()
                )
            else:
                _error_result(
                    f"Unknown view '{view}'. Valid views: inbox, today, tomorrow, upcoming, anytime, someday, logbook, trash, deadlines"
                )

            if not todos:
                todos = []

            # Filter by context (tag)
            if context:
                context_tags = [context] if isinstance(context, str) else context
                todos = [
                    t
                    for t in todos
                    if any(tag in (t.get("tags") or []) for tag in context_tags)
                ]

            # Filter by energy tag
            if energy:
                todos = [t for t in todos if energy in (t.get("tags") or [])]

            # Filter by time available tag
            if time_available:
                todos = [t for t in todos if time_available in (t.get("tags") or [])]

            # Filter by area
            if area:
                todos = [
                    t
                    for t in todos
                    if t.get("area") == area or t.get("area_title") == area
                ]

            # Filter by project
            if project:
                todos = [
                    t
                    for t in todos
                    if t.get("project") == project or t.get("project_title") == project
                ]

            # Filter completed unless requested
            if not include_completed and view not in ("logbook",):
                todos = [t for t in todos if t.get("status") != "completed"]

            if not todos:
                filters = []
                if view:
                    filters.append(f"view={view}")
                if context:
                    filters.append(f"context={context}")
                if energy:
                    filters.append(f"energy={energy}")
                filter_str = ", ".join(filters) if filters else "no filters"
                empty_text = (
                    f"No tasks found ({filter_str}). Try different filters or "
                    "add tasks with capture-task."
                )
                return make_result(
                    data=[],
                    summary=f"No tasks found ({filter_str}).",
                    text=empty_text,
                )

            # Apply limit
            effective_limit = min(max(1, limit), 200)
            total_count = len(todos)
            shown = todos[:effective_limit]

            # Build legacy text block (preserved verbatim).
            text_header = f"**{total_count} task{'s' if total_count != 1 else ''}**"
            if view:
                text_header += f" in {view}"
            if context:
                text_header += f" with context {context}"
            if total_count > effective_limit:
                text_header += f" (showing first {effective_limit})"
            text_header += "\n\n"

            text_body = text_header + "\n\n---\n\n".join(
                render_todo(todo) for todo in shown
            )
            if total_count > effective_limit:
                text_body += (
                    f"\n\n*...and {total_count - effective_limit} more tasks. "
                    "Use limit= to see more.*"
                )

            # Build structured payload.
            data = [to_dict_todo(t) for t in shown]
            summary_parts = [f"{total_count} task{'s' if total_count != 1 else ''}"]
            if view:
                summary_parts.append(f"in {view}")
            if context:
                summary_parts.append(f"with context {context}")
            summary = " ".join(summary_parts)
            if total_count > effective_limit:
                summary += f" (showing first {effective_limit})"

            meta: dict = {
                "total_count": total_count,
                "shown": len(shown),
            }
            if total_count > effective_limit:
                meta["truncated"] = True

            return make_result(
                data=data,
                summary=summary,
                meta=meta,
                text=text_body,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in get-tasks", exc_info=True)
            _error_result("Failed to fetch tasks. Check server logs for details.")

    @mcp.tool(
        name="focus-mode",
        annotations=TOOL_ANNOTATIONS["focus-mode"],
        tags=tags_for("focus-mode"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[FocusResult]),
    )
    async def focus_mode(
        context: Optional[str] = None,
        energy: Optional[str] = None,
        time_available: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Get the single most important task to work on right now.

        GTD Stage: Engage
        Use when: Feeling overwhelmed or asking "what should I do next?"

        Priority order:
        1. Overdue tasks with deadline (oldest first)
        2. Today's tasks with deadline (earliest deadline first)
        3. Today's tasks without deadline
        4. Anytime tasks (next actions)

        Args:
            context: Current GTD context (e.g., "@computer", "@phone")
            energy: Current energy level (e.g., "high-energy", "low-energy")
            time_available: Available time (e.g., "5min", "15min", "30min")
        """
        if ctx:
            await ctx.info("Finding your most important task...")

        try:
            from datetime import date

            today_str = date.today().isoformat()
            selected_task = None
            selection_reason = ""
            selection_kind: Optional[
                Literal["overdue", "today_with_deadline", "today", "anytime"]
            ] = None

            # 1. Check for overdue tasks with deadlines
            all_todos = db.todos(status="incomplete")
            overdue = [
                t
                for t in all_todos
                if t.get("deadline") and t.get("deadline") < today_str
            ]

            # Apply context/energy/time filters
            def matches_filters(task):
                if context and context not in (task.get("tags") or []):
                    return False
                if energy and energy not in (task.get("tags") or []):
                    return False
                if time_available and time_available not in (task.get("tags") or []):
                    return False
                return True

            overdue = [t for t in overdue if matches_filters(t)]
            if overdue:
                selected_task = sorted(overdue, key=lambda t: t.get("deadline", ""))[0]
                selection_reason = (
                    f"OVERDUE (deadline was {selected_task.get('deadline')})"
                )
                selection_kind = "overdue"

            # 2. Check today's tasks with deadlines
            if not selected_task:
                today_tasks = db.today()
                today_with_deadline = [
                    t
                    for t in today_tasks
                    if t.get("deadline") == today_str and matches_filters(t)
                ]
                if today_with_deadline:
                    selected_task = today_with_deadline[0]
                    selection_reason = "Due TODAY with deadline"
                    selection_kind = "today_with_deadline"

            # 3. Check today's tasks without deadlines
            if not selected_task:
                today_tasks = db.today()
                today_no_deadline = [
                    t
                    for t in today_tasks
                    if not t.get("deadline") and matches_filters(t)
                ]
                if today_no_deadline:
                    selected_task = today_no_deadline[0]
                    selection_reason = "Scheduled for today"
                    selection_kind = "today"

            # 4. Check anytime tasks
            if not selected_task:
                anytime_tasks = db.anytime()
                anytime_filtered = [t for t in anytime_tasks if matches_filters(t)]
                if anytime_filtered:
                    selected_task = anytime_filtered[0]
                    selection_reason = "Next available action"
                    selection_kind = "anytime"

            if not selected_task:
                filter_desc = []
                if context:
                    filter_desc.append(f"context={context}")
                if energy:
                    filter_desc.append(f"energy={energy}")
                if time_available:
                    filter_desc.append(f"time={time_available}")

                filter_str = (
                    ", ".join(filter_desc) if filter_desc else "current filters"
                )
                empty_text = (
                    f"No tasks match {filter_str}.\n\n"
                    "Try:\n"
                    "- Different context (remove context filter)\n"
                    "- Check if tasks need context tags\n"
                    "- Use get-tasks(view='anytime') to see all available tasks"
                )
                return make_result(
                    data=None,
                    summary=f"No tasks match {filter_str}.",
                    text=empty_text,
                )

            # Enrich the focused task with checklist (detail view).
            enriched = dict(selected_task)
            try:
                enriched["checklist"] = db.checklist_items(enriched["uuid"]) or []
            except Exception:
                enriched["checklist"] = []

            # Format the focused task with context
            output = f"**FOCUS: {selection_reason}**\n\n"
            output += render_todo(enriched)

            # Add project context if applicable
            if selected_task.get("project"):
                output += (
                    "\n\n*Part of project: "
                    f"{selected_task.get('project_title', selected_task.get('project'))}*"
                )

            todo_dict = to_dict_todo(enriched)
            payload = FocusResult(
                task=todo_dict,
                selection_reason=selection_kind,
                selection_detail=selection_reason,
            )
            summary = f"Focus task: {enriched.get('title', '')} ({selection_reason})"
            return make_result(
                data=payload.model_dump(),
                summary=summary,
                text=output,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in focus-mode", exc_info=True)
            _error_result("Failed to find focus task. Check server logs for details.")

    @mcp.tool(
        name="complete-task",
        annotations=TOOL_ANNOTATIONS["complete-task"],
        tags=tags_for("complete-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def complete_task(
        task_id: Optional[str] = None,
        task_title: Optional[str] = None,
        completion_notes: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Mark a task as complete.

        GTD Stage: Engage
        Use when: Finishing a task. Provide task_id if known, or task_title to search.
        Provide at least one of task_id or task_title to identify the task.

        Args:
            task_id: UUID of the task to complete (preferred if known)
            task_title: Title to search for (fuzzy match). If multiple match, returns list.
            completion_notes: Optional notes to append before completing
        """
        if ctx:
            await ctx.info("Completing task...")

        if not task_id and not task_title:
            _error_result("Provide either task_id or task_title to identify the task.")

        try:
            # If title provided, search for matching task
            if task_title and not task_id:
                matches = db.todos(status="incomplete")
                matches = [
                    t
                    for t in matches
                    if task_title.lower() in t.get("title", "").lower()
                ]

                if len(matches) == 0:
                    # CDI-1255: distinguish a genuine miss from a possibly-stale
                    # index. If something was just written, the on-disk SQLite
                    # snapshot may be behind — say so instead of a false negative.
                    stale = db.index_stale()
                    if stale:
                        no_match = (
                            f"No task found matching '{task_title}' yet — a task was "
                            "captured very recently and Things may not have flushed "
                            "it to the read index. Wait a moment and retry, or pass "
                            "task_id directly."
                        )
                        summary_msg = (
                            f"No task found matching '{task_title}' "
                            "(index may be stale)."
                        )
                    else:
                        no_match = (
                            f"No task found matching '{task_title}'.\n\n"
                            "Use search-tasks to find the correct task, or check "
                            "get-tasks(view='logbook') if already completed."
                        )
                        summary_msg = f"No task found matching '{task_title}'."
                    return make_result(
                        data=WriteResult(
                            acknowledged=False,
                            thing_id=None,
                            summary=summary_msg,
                        ).model_dump(),
                        summary=summary_msg,
                        text=no_match,
                        meta={"index_stale": stale},
                    )

                if len(matches) > 1:
                    text_body = (
                        f"Found {len(matches)} tasks matching '{task_title}'. "
                        "Please specify:\n\n"
                    )
                    for t in matches[:5]:
                        text_body += f"- **{t.get('title')}** (ID: `{t.get('uuid')}`)\n"
                    if len(matches) > 5:
                        text_body += f"\n...and {len(matches) - 5} more."
                    return make_result(
                        data=WriteResult(
                            acknowledged=False,
                            thing_id=None,
                            summary=f"Multiple tasks matched '{task_title}'.",
                        ).model_dump(),
                        summary=f"Found {len(matches)} tasks matching '{task_title}'.",
                        text=text_body,
                        meta={"match_count": len(matches)},
                    )

                task_id = matches[0].get("uuid")

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Append completion notes if provided
            if completion_notes:
                url = update_todo(
                    id=task_id, append_notes=f"\n[Completed] {completion_notes}"
                )
                execute_url(url)

            # Mark as completed
            url = update_todo(id=task_id, completed=True)
            success = execute_url(url)

            if not success:
                _error_result("Failed to complete task")

            # Invalidate caches
            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime"]
            )

            # Track triage action
            try:
                task_data = db.get(task_id) or {}
                triage_tracker.record(
                    task_id=task_id,
                    task_title=task_data.get("title", task_title or ""),
                    task_notes=task_data.get("notes"),
                    task_tags=task_data.get("tags"),
                    action="completed",
                    action_details={"completion_notes": bool(completion_notes)},
                )
            except Exception:
                logger.debug("Triage tracking failed (non-critical)")

            summary = "Task completed successfully. Keep up the momentum!"
            return write_result(
                summary=summary,
                thing_id=task_id,
                acknowledged=True,
                text=summary,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error completing task", exc_info=True)
            _error_result("Failed to complete task. Check server logs for details.")

    # --- GTD CAPTURE STAGE ---

    @mcp.tool(
        name="capture-task",
        annotations=TOOL_ANNOTATIONS["capture-task"],
        tags=tags_for("capture-task"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def capture_task(
        title: str,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        when: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Quick capture a task to Inbox for later processing.

        GTD Stage: Capture
        Use when: Getting something out of your head quickly. Don't organize now.
        Instead use: schedule-task if you already know when/where it belongs.

        Args:
            title: What needs to be done (required)
            notes: Additional details (optional)
            tags: Context tags like @computer, @phone (optional)
            when: Optional schedule (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD). If omitted, goes to inbox.
        """
        if ctx:
            await ctx.info(f"Capturing to inbox: {title[:30]}...")

        try:
            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Ensure tags exist
            if tags:
                ensure_tags_exist(tags)

            # Create task (no when/list specified = inbox)
            url = add_todo(title=title, notes=notes, tags=tags, when=when)
            success = execute_url(url)

            if not success:
                _error_result("Failed to capture task")

            invalidate_caches_for(["get-inbox", "get-tasks"])

            # Record in the write overlay so this item is visible to same-session
            # reads (search-tasks / get-tasks / fuzzy task_title) before Things
            # flushes it to SQLite. CDI-1255: read-your-writes consistency.
            record_write(title, when=when, tags=tags, notes=notes)

            if when:
                summary = f"Captured and scheduled: {title} ({when})"
                text_body = (
                    f"Captured and scheduled: {title} ({when})\n\n"
                    "Task is scheduled — no further inbox processing needed."
                )
            else:
                summary = f"Captured to Inbox: {title}"
                text_body = (
                    f"Captured to Inbox: {title}\n\n"
                    "Use process-inbox or schedule-task to clarify and organize."
                )
            return write_result(
                summary=summary,
                thing_id=None,
                acknowledged=True,
                text=text_body,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error capturing task", exc_info=True)
            _error_result("Failed to capture task. Check server logs for details.")

    # --- GTD CLARIFY STAGE ---

    @mcp.tool(
        name="process-inbox",
        annotations=TOOL_ANNOTATIONS["process-inbox"],
        tags=tags_for("process-inbox"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[Union[Todo, list[Todo]]]),
    )
    async def process_inbox(
        all: bool = False,
        limit: int = 50,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Process inbox items using GTD methodology.

        GTD Stage: Clarify
        Use when: Processing inbox during daily/weekly review.
        For automated batch triage, call with all=True then pass decisions to bulk-triage.

        Args:
            all: If True, return all inbox items in compact format for bulk-triage. Default: False (one item at a time).
            limit: Maximum items to return when all=True (default 50, max 200).

        Returns the oldest inbox item with GTD decision guidance (default), or all items in compact format.
        """
        if ctx:
            await ctx.info("Processing inbox...")

        try:
            inbox_items = db.inbox()

            if not inbox_items:
                # Surface triage insights at inbox-zero moment
                inbox_zero_msg = (
                    "**Inbox is clear!** GTD: Mind like water achieved.\n\n"
                    "Your inbox is empty. Use capture-task when new items come up."
                )
                try:
                    summary_data = triage_tracker.get_summary(days=7)
                    if summary_data["total"] > 0:
                        total = summary_data["total"]
                        top_action = (
                            max(
                                summary_data["actions"],
                                key=summary_data["actions"].get,
                            )
                            if summary_data["actions"]
                            else None
                        )
                        inbox_zero_msg += f"\n\n*This week: {total} items triaged"
                        if top_action:
                            inbox_zero_msg += f", mostly {top_action}"
                        inbox_zero_msg += f". View trends at {get_dashboard_url()}*"
                except Exception:
                    pass
                return make_result(
                    data=[],
                    summary="Inbox is clear.",
                    text=inbox_zero_msg,
                    meta={"remaining": 0},
                )

            # Track inbox view for source detection
            try:
                triage_tracker.record_inbox_view()
            except Exception:
                logger.debug("Triage inbox view tracking failed (non-critical)")

            if all:
                # Return all items in compact format for bulk-triage
                effective_limit = min(max(1, limit), 200)
                total_count = len(inbox_items)
                items_to_show = inbox_items[:effective_limit]

                output = f"**Inbox: {total_count} items**"
                if total_count > effective_limit:
                    output += f" (showing first {effective_limit})"
                output += (
                    "\n\nUse `bulk-triage` with decisions for each item below.\n\n"
                )

                output += "**GTD Decision Tree** (apply to each item):\n"
                output += (
                    "- Not actionable: `cancel`, `defer` (someday), or add notes\n"
                )
                output += "- Multi-step: `assign` (convert to project)\n"
                output += "- <2 min: do it, then `complete`\n"
                output += "- Delegate: `delegate` | Schedule: `schedule` or `defer`\n\n"

                output += "**Items:**\n\n"
                for i, item in enumerate(items_to_show, 1):
                    title = item.get("title", "Untitled")
                    uuid = item.get("uuid", "")
                    notes_preview = ""
                    if item.get("notes"):
                        notes_preview = f" — {item['notes'][:80]}..."
                    tags_str = ""
                    if item.get("tags"):
                        tags_str = f" [{', '.join(item['tags'])}]"
                    output += f"{i}. **{title}** (`{uuid}`){tags_str}{notes_preview}\n"

                if total_count > effective_limit:
                    output += (
                        f"\n*...and {total_count - effective_limit} more items. "
                        "Call again with higher limit or process remaining after.*"
                    )

                data = [to_dict_todo(t) for t in items_to_show]
                summary = f"{total_count} inbox item{'s' if total_count != 1 else ''}"
                if total_count > effective_limit:
                    summary += f" (showing first {effective_limit})"
                meta = {
                    "total_count": total_count,
                    "shown": len(items_to_show),
                }
                if total_count > effective_limit:
                    meta["truncated"] = True
                return make_result(data=data, summary=summary, meta=meta, text=output)

            # Default: one item at a time
            item = inbox_items[0]
            remaining = len(inbox_items) - 1

            # Enrich with checklist for the single-item detail view.
            enriched = dict(item)
            try:
                enriched["checklist"] = db.checklist_items(enriched["uuid"]) or []
            except Exception:
                enriched["checklist"] = []

            output = (
                f"**Processing Inbox** ({remaining} item"
                f"{'s' if remaining != 1 else ''} remaining)\n\n"
            )
            output += render_todo(enriched)
            output += "\n\n---\n\n"
            output += "**GTD Decision Tree:**\n\n"
            output += "1. **Is this actionable?**\n"
            output += "   - No, trash it -> Use modify-task with canceled=true\n"
            output += "   - No, maybe later -> Use defer-task with defer_to='someday'\n"
            output += "   - No, reference -> Add to notes elsewhere\n"
            output += "   - **Yes, it's actionable ->** Continue...\n\n"
            output += "2. **Is it a single action or multi-step?**\n"
            output += "   - Multi-step -> Use convert-to-project\n"
            output += "   - **Single action ->** Continue...\n\n"
            output += "3. **Can it be done in <2 minutes?**\n"
            output += "   - Yes -> **Do it now!** Then complete-task\n"
            output += "   - No, delegate -> Use delegate-task\n"
            output += "   - No, schedule -> Use schedule-task\n"
            output += (
                "\n*Organize tip: If this is a next action for an existing project, "
            )
            output += "use `schedule-task` with `project=` to add it directly.*\n"

            return make_result(
                data=to_dict_todo(enriched),
                summary=(
                    f"Processing inbox: {enriched.get('title', 'Untitled')} "
                    f"({remaining} remaining)"
                ),
                meta={"remaining": remaining},
                text=output,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error processing inbox", exc_info=True)
            _error_result("Failed to process inbox. Check server logs for details.")

    @mcp.tool(
        name="convert-to-project",
        annotations=TOOL_ANNOTATIONS["convert-to-project"],
        tags=tags_for("convert-to-project"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[WriteResult]),
    )
    async def convert_to_project(
        task_id: str,
        first_action: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Convert a task into a project when it requires multiple steps.

        GTD Stage: Clarify
        Use when: Realizing a task is actually a multi-step outcome.
        GTD rule: Any outcome requiring >1 action is a project.

        Preserves from the original task:
        - Title becomes project title
        - Notes, tags, and area are transferred
        - Deadline becomes project deadline (not on child tasks)
        - Incomplete checklist items become project tasks

        Args:
            task_id: UUID of the task to convert
            first_action: Title of the first next action (added before checklist items)
        """
        if ctx:
            await ctx.info("Converting task to project...")

        try:
            # Get the original task
            task = db.get(task_id)
            if not task:
                _error_result(f"Task not found: {task_id}")

            if task.get("type") != "to-do":
                _error_result("Can only convert to-do items to projects")

            # Ensure Things app is running
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            # Create project with task's details
            project_title = task.get("title", "New Project")
            project_notes = task.get("notes", "")
            project_deadline = task.get("deadline")

            # Get checklist items from the original task
            checklist_items = db.checklist_items(task_id)

            # Build tasks array for the project
            tasks = []
            if first_action:
                tasks.append({"title": first_action, "when": "anytime"})

            # Convert checklist items to project tasks (incomplete ones only)
            for item in checklist_items:
                if item.get("status") != "completed":
                    tasks.append({"title": item.get("title", ""), "when": "anytime"})

            # Ensure tags exist before creating the project
            project_tags = task.get("tags")
            if project_tags:
                ensure_tags_exist(project_tags)

            # Use JSON API for atomic creation
            url = add_project_with_tasks(
                title=project_title,
                tasks=tasks,
                notes=project_notes,
                deadline=project_deadline,
                tags=project_tags,
                area=task.get("area_title"),
            )
            success = execute_url(url)

            if not success:
                _error_result("Failed to create project")

            # Delete/cancel the original task
            cancel_url = update_todo(id=task_id, canceled=True)
            execute_url(cancel_url)

            invalidate_caches_for(["get-inbox", "get-projects", "get-tasks"])

            # Track triage action
            try:
                triage_tracker.record(
                    task_id=task_id,
                    task_title=task.get("title", ""),
                    task_notes=task.get("notes"),
                    task_tags=task.get("tags"),
                    action="converted-to-project",
                    action_details={"first_action": bool(first_action)},
                )
            except Exception:
                logger.debug("Triage tracking failed (non-critical)")

            # Build result message
            result_text = f"Converted '{project_title}' to project."
            if project_deadline:
                result_text += f"\nDeadline: {project_deadline}"

            checklist_count = len(
                [i for i in checklist_items if i.get("status") != "completed"]
            )
            if first_action and checklist_count > 0:
                result_text += (
                    f"\nTasks: {first_action} + {checklist_count} from checklist"
                )
            elif first_action:
                result_text += f"\nFirst action: {first_action}"
            elif checklist_count > 0:
                result_text += (
                    f"\nConverted {checklist_count} checklist items to tasks."
                )
            else:
                result_text += (
                    "\n\n**Warning:** Project has no next action. GTD requires every "
                    "project to have a clear next step. Use schedule-task to add one."
                )

            # Post-conversion guidance
            result_text += (
                "\n\nUse `modify-project` to assign an area, set a deadline, "
                "or edit properties."
            )
            if not task.get("area_title"):
                result_text += (
                    "\nThis project has no area of focus — consider assigning one "
                    "with `modify-project`."
                )

            summary = f"Converted '{project_title}' to project"
            meta: dict = {
                "checklist_items_converted": checklist_count,
                "has_first_action": bool(first_action),
                "has_area": bool(task.get("area_title")),
            }
            return write_result(
                summary=summary,
                thing_id=None,  # JSON-API doesn't return the new project's UUID
                acknowledged=True,
                text=result_text,
                meta=meta,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error converting to project", exc_info=True)
            _error_result(
                "Failed to convert to project. Check server logs for details."
            )
