#!/usr/bin/env python3
"""
Things MCP Server implementation using the FastMCP pattern.
This provides a more modern and maintainable approach to the Things integration.
"""

from typing import Dict, Any, Optional, List, Union
import things

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
import mcp.types as types

# Import supporting modules
from .formatters import format_todo, format_project, format_area, format_tag
from .utils import app_state
from .url_scheme import (
    add_todo,
    add_project,
    update_todo,
    update_project,
    show,
    search,
    launch_things,
    execute_url,
    add_project_with_tasks,
)

# Import and configure enhanced logging
from .logging_config import (
    setup_logging,
    get_logger,
    log_operation_start,
    log_operation_end,
)

# Import caching
from .cache import cached, invalidate_caches_for, get_cache_stats, CACHE_TTL
from .tag_handler import ensure_tags_exist

# Import settings (pydantic-settings loads .env automatically)
from .settings import get_settings

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

# n8n compatibility: Parameters that n8n's MCP Client Tool incorrectly sends
# See: https://github.com/n8n-io/n8n/issues/21500
N8N_EXTRA_PARAMS = {"toolCallId", "sessionId", "action", "chatInput"}

# Configure enhanced logging
setup_logging(console_level="INFO", file_level="DEBUG", structured_logs=True)
logger = get_logger(__name__)


INSTRUCTIONS_TEXT = (
    "### Things MCP Server - GTD-Native Task Management\n\n"
    "A GTD (Getting Things Done) aligned server for Things 3 on macOS. Tools map to GTD's 5 stages:\n\n"
    "**GTD Workflow Tools**\n"
    "- **Capture**: `capture-task` - Quick inbox capture\n"
    "- **Clarify**: `process-inbox` - Process items with GTD decision tree\n"
    "- **Organize**: `schedule-task`, `delegate-task`, `defer-task`, `plan-project`\n"
    "- **Reflect**: `daily-review`, `weekly-review` - GTD-compliant reviews\n"
    "- **Engage**: `get-tasks`, `focus-mode`, `complete-task` - Context-first task selection\n\n"
    "**GTD Context Tags**\n"
    "Filter tasks by context: @computer, @phone, @office, @home, @errands, @anywhere\n"
    "Use `get-tasks(context='@computer')` to see what you can do at your desk.\n\n"
    "**Waiting For**\n"
    "Use `delegate-task` to track items you're waiting on others to complete.\n\n"
    "**Limitations**\n"
    "- Requires Things 3 for macOS with scripting permissions\n"
    "- Local data only; attachments unavailable\n"
    "- Some operations take a few seconds via URL scheme\n\n"
    "**Support**: https://github.com/CaseyRo/things-fastmcp/issues\n"
)

WEBSITE_URL = "https://github.com/CaseyRo/things-fastmcp"

# Type alias supporting both newer FastMCP installs (with mcp.types.Icon)
# and older releases that still expect simple dictionaries for icon metadata.
IconLike = Union[Any, Dict[str, Any]]


def _build_icon(
    src: str, *, sizes: Optional[List[str]] = None, mime_type: Optional[str] = None
) -> IconLike:
    """Create an icon instance compatible with the available MCP types module."""
    icon_cls = getattr(types, "Icon", None)
    if icon_cls is not None:
        return icon_cls(src=src, sizes=sizes, mimeType=mime_type)

    # Fall back to a plain dictionary for environments running an older MCP build
    # that predates the Icon model.
    icon_data: Dict[str, Any] = {"src": src}
    if sizes:
        icon_data["sizes"] = sizes
    if mime_type:
        icon_data["mimeType"] = mime_type
    return icon_data


ICONS: List[IconLike] = [
    _build_icon(
        src="https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/72x72/1F4DD.png",
        sizes=["64x64"],
    ),
]


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling.

    FastMCP v3 uses ToolError for proper error propagation to clients.
    """
    raise ToolError(message)


# Default values for documentation purposes
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8009
HOST_ENV_VAR = "THINGS_FASTMCP_HOST"


def get_binding_host() -> str:
    """Return the host for the FastMCP server from settings."""
    return get_settings().things_fastmcp_host


def get_binding_port() -> int:
    """Return the port for the FastMCP server from settings."""
    return get_settings().things_fastmcp_port


def _create_fastmcp_instance() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    server = FastMCP(
        "Things",
        instructions=INSTRUCTIONS_TEXT,
        website_url=WEBSITE_URL,
        icons=ICONS,
    )

    # Add n8n compatibility middleware
    # This strips extra parameters that n8n incorrectly sends (toolCallId, sessionId, etc.)
    # See: https://github.com/n8n-io/n8n/issues/21500
    class N8NCompatibilityMiddleware(Middleware):
        """Strip extra parameters that n8n's MCP Client Tool incorrectly sends."""

        async def on_call_tool(self, context, call_next):
            if hasattr(context, "message") and hasattr(context.message, "arguments"):
                args = context.message.arguments
                if args:
                    # Remove n8n-specific parameters that cause Pydantic validation errors
                    for param in list(N8N_EXTRA_PARAMS):
                        if param in args:
                            del args[param]
                            logger.debug(
                                f"Stripped n8n parameter '{param}' from tool call"
                            )
            return await call_next(context)

    try:
        server.add_middleware(N8NCompatibilityMiddleware())
        logger.info("n8n compatibility middleware registered")
    except Exception as e:
        logger.warning(f"Could not register n8n middleware: {e}")

    return server


# Create the FastMCP server
mcp = _create_fastmcp_instance()


# =============================================================================
# GTD-NATIVE TOOLS
# =============================================================================

# --- GTD ENGAGE STAGE ---


@mcp.tool(name="get-tasks", annotations=TOOL_ANNOTATIONS["get-tasks"], timeout=5)
async def get_tasks(
    view: Optional[str] = None,
    context: Optional[Union[str, List[str]]] = None,
    energy: Optional[str] = None,
    time_available: Optional[str] = None,
    area: Optional[str] = None,
    project: Optional[str] = None,
    include_completed: bool = False,
    ctx: Context = None,
) -> str:
    """Get tasks filtered by view, context, energy, and time available.

    GTD Stage: Engage
    Use when: Choosing what to work on based on current context and constraints.

    Context is your FIRST filter in GTD. Common contexts:
    - @computer, @phone, @office, @home, @errands, @anywhere

    Args:
        view: Task view - inbox, today, tomorrow, upcoming, anytime, someday, logbook, trash, deadlines
        context: GTD context tag(s) to filter by (e.g., "@computer", "@phone")
        energy: Energy level tag (e.g., "high-energy", "low-energy")
        time_available: Time estimate tag (e.g., "5min", "15min", "30min", "1hr+")
        area: Filter by area name or UUID
        project: Filter by project name or UUID
        include_completed: Include completed tasks (default False)

    Examples:
        get_tasks(view="today") - What's scheduled for today?
        get_tasks(context="@computer") - What can I do at my desk?
        get_tasks(view="anytime", context="@errands") - What can I do while out?
        get_tasks(context="waiting-for") - What am I waiting on others for?
    """
    if ctx:
        await ctx.info(f"Fetching tasks (view={view}, context={context})...")

    try:
        # Build query based on view
        if view == "inbox":
            todos = things.inbox()
        elif view == "today":
            todos = things.today()
        elif view == "tomorrow":
            # Things doesn't have a direct tomorrow() function
            todos = things.upcoming()
            # Filter to tomorrow only
            from datetime import date, timedelta

            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            todos = [t for t in todos if t.get("start_date") == tomorrow]
        elif view == "upcoming":
            todos = things.upcoming()
        elif view == "anytime":
            todos = things.anytime()
        elif view == "someday":
            todos = things.someday()
        elif view == "logbook":
            todos = (
                things.logbook()
                if hasattr(things, "logbook")
                else things.last("7d", status="completed")
            )
        elif view == "trash":
            todos = things.trash()
        elif view == "deadlines":
            # Get tasks with deadlines
            todos = things.todos(deadline=True)
        elif view is None:
            # No view specified, get all incomplete tasks
            todos = (
                things.todos(status="incomplete")
                if not include_completed
                else things.todos()
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
                t for t in todos if t.get("area") == area or t.get("area_title") == area
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
            return f"No tasks found ({filter_str}). Try different filters or add tasks with capture-task."

        # Format output with summary
        summary = f"**{len(todos)} task{'s' if len(todos) != 1 else ''}**"
        if view:
            summary += f" in {view}"
        if context:
            summary += f" with context {context}"
        summary += "\n\n"

        formatted_todos = [format_todo(todo) for todo in todos]
        return summary + "\n\n---\n\n".join(formatted_todos)

    except Exception as e:
        logger.error(f"Error in get-tasks: {str(e)}")
        _error_result(f"Error fetching tasks: {str(e)}")


@mcp.tool(name="focus-mode", annotations=TOOL_ANNOTATIONS["focus-mode"], timeout=5)
async def focus_mode(
    context: Optional[str] = None,
    energy: Optional[str] = None,
    time_available: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Get the single most important task to work on right now.

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

        # 1. Check for overdue tasks with deadlines
        all_todos = things.todos(status="incomplete")
        overdue = [
            t for t in all_todos if t.get("deadline") and t.get("deadline") < today_str
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
            selection_reason = f"OVERDUE (deadline was {selected_task.get('deadline')})"

        # 2. Check today's tasks with deadlines
        if not selected_task:
            today_tasks = things.today()
            today_with_deadline = [
                t
                for t in today_tasks
                if t.get("deadline") == today_str and matches_filters(t)
            ]
            if today_with_deadline:
                selected_task = today_with_deadline[0]
                selection_reason = "Due TODAY with deadline"

        # 3. Check today's tasks without deadlines
        if not selected_task:
            today_tasks = things.today()
            today_no_deadline = [
                t for t in today_tasks if not t.get("deadline") and matches_filters(t)
            ]
            if today_no_deadline:
                selected_task = today_no_deadline[0]
                selection_reason = "Scheduled for today"

        # 4. Check anytime tasks
        if not selected_task:
            anytime_tasks = things.anytime()
            anytime_filtered = [t for t in anytime_tasks if matches_filters(t)]
            if anytime_filtered:
                selected_task = anytime_filtered[0]
                selection_reason = "Next available action"

        if not selected_task:
            filter_desc = []
            if context:
                filter_desc.append(f"context={context}")
            if energy:
                filter_desc.append(f"energy={energy}")
            if time_available:
                filter_desc.append(f"time={time_available}")

            filter_str = ", ".join(filter_desc) if filter_desc else "current filters"
            return (
                f"No tasks match {filter_str}.\n\n"
                "Try:\n"
                "- Different context (remove context filter)\n"
                "- Check if tasks need context tags\n"
                "- Use get-tasks(view='anytime') to see all available tasks"
            )

        # Format the focused task with context
        output = f"**FOCUS: {selection_reason}**\n\n"
        output += format_todo(selected_task)

        # Add project context if applicable
        if selected_task.get("project"):
            output += f"\n\n*Part of project: {selected_task.get('project_title', selected_task.get('project'))}*"

        return output

    except Exception as e:
        logger.error(f"Error in focus-mode: {str(e)}")
        _error_result(f"Error finding focus task: {str(e)}")


@mcp.tool(
    name="complete-task", annotations=TOOL_ANNOTATIONS["complete-task"], timeout=30
)
async def complete_task(
    task_id: Optional[str] = None,
    task_title: Optional[str] = None,
    completion_notes: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Mark a task as complete.

    GTD Stage: Engage
    Use when: Finishing a task. Provide task_id if known, or task_title to search.

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
            matches = things.todos(status="incomplete")
            matches = [
                t for t in matches if task_title.lower() in t.get("title", "").lower()
            ]

            if len(matches) == 0:
                return (
                    f"No task found matching '{task_title}'.\n\n"
                    "Use search-tasks to find the correct task, or check "
                    "get-tasks(view='logbook') if already completed."
                )

            if len(matches) > 1:
                result = f"Found {len(matches)} tasks matching '{task_title}'. Please specify:\n\n"
                for t in matches[:5]:
                    result += f"- **{t.get('title')}** (ID: `{t.get('uuid')}`)\n"
                if len(matches) > 5:
                    result += f"\n...and {len(matches) - 5} more."
                return result

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
        invalidate_caches_for(["get-tasks", "get-today", "get-inbox", "get-anytime"])

        return "Task completed successfully. Keep up the momentum!"

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error completing task: {str(e)}")
        _error_result(f"Error completing task: {str(e)}")


# --- GTD CAPTURE STAGE ---


@mcp.tool(name="capture-task", annotations=TOOL_ANNOTATIONS["capture-task"], timeout=30)
async def capture_task(
    title: str,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
    ctx: Context = None,
) -> str:
    """Quick capture a task to Inbox for later processing.

    GTD Stage: Capture
    Use when: Getting something out of your head quickly. Don't organize now.
    Instead use: schedule-task if you already know when/where it belongs.

    Args:
        title: What needs to be done (required)
        notes: Additional details (optional)
        tags: Context tags like @computer, @phone (optional)
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

        # Create in inbox (no when/list specified = inbox)
        url = add_todo(title=title, notes=notes, tags=tags)
        success = execute_url(url)

        if not success:
            _error_result("Failed to capture task")

        invalidate_caches_for(["get-inbox", "get-tasks"])

        return (
            f"Captured to Inbox: {title}\n\n"
            "Use process-inbox or schedule-task to clarify and organize."
        )

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error capturing task: {str(e)}")
        _error_result(f"Error capturing task: {str(e)}")


# --- GTD CLARIFY STAGE ---


@mcp.tool(
    name="process-inbox", annotations=TOOL_ANNOTATIONS["process-inbox"], timeout=5
)
async def process_inbox(ctx: Context = None) -> str:
    """Process the oldest inbox item using GTD methodology.

    GTD Stage: Clarify
    Use when: Processing inbox during daily/weekly review.

    Returns the oldest inbox item with GTD decision guidance:
    1. Is this actionable?
       - No → Trash (delete), Someday (defer), or Reference (add notes)
    2. Is it a single action or multi-step project?
       - Project → Use convert-to-project
    3. Can it be done in <2 minutes?
       - Yes → Do it now!
       - No → Delegate (delegate-task) or Defer (schedule-task)
    """
    if ctx:
        await ctx.info("Processing inbox...")

    try:
        inbox_items = things.inbox()

        if not inbox_items:
            return (
                "**Inbox is clear!** GTD: Mind like water achieved.\n\n"
                "Your inbox is empty. Use capture-task when new items come up."
            )

        # Get oldest item (first in list, Things orders by creation)
        item = inbox_items[0]
        remaining = len(inbox_items) - 1

        output = f"**Processing Inbox** ({remaining} item{'s' if remaining != 1 else ''} remaining)\n\n"
        output += format_todo(item)
        output += "\n\n---\n\n"
        output += "**GTD Decision Tree:**\n\n"
        output += "1. **Is this actionable?**\n"
        output += "   - No, trash it → Use update-todo with canceled=true\n"
        output += "   - No, maybe later → Use defer-task with defer_to='someday'\n"
        output += "   - No, reference → Add to notes elsewhere\n"
        output += "   - **Yes, it's actionable →** Continue...\n\n"
        output += "2. **Is it a single action or multi-step?**\n"
        output += "   - Multi-step → Use convert-to-project\n"
        output += "   - **Single action →** Continue...\n\n"
        output += "3. **Can it be done in <2 minutes?**\n"
        output += "   - Yes → **Do it now!** Then complete-task\n"
        output += "   - No, delegate → Use delegate-task\n"
        output += "   - No, schedule → Use schedule-task\n"

        return output

    except Exception as e:
        logger.error(f"Error processing inbox: {str(e)}")
        _error_result(f"Error processing inbox: {str(e)}")


@mcp.tool(
    name="convert-to-project",
    annotations=TOOL_ANNOTATIONS["convert-to-project"],
    timeout=30,
)
async def convert_to_project(
    task_id: str,
    first_action: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Convert a task into a project when it requires multiple steps.

    GTD Stage: Clarify
    Use when: Realizing a task is actually a multi-step outcome.
    GTD rule: Any outcome requiring >1 action is a project.

    Args:
        task_id: UUID of the task to convert
        first_action: Title of the first next action (recommended)
    """
    if ctx:
        await ctx.info("Converting task to project...")

    try:
        # Get the original task
        task = things.get(task_id)
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

        # Build tasks array for the project
        tasks = []
        if first_action:
            tasks.append({"title": first_action, "when": "anytime"})

        # Use JSON API for atomic creation
        url = add_project_with_tasks(
            title=project_title,
            tasks=tasks,
            notes=project_notes,
            tags=task.get("tags"),
            area=task.get("area_title"),
        )
        success = execute_url(url)

        if not success:
            _error_result("Failed to create project")

        # Delete/cancel the original task
        cancel_url = update_todo(id=task_id, canceled=True)
        execute_url(cancel_url)

        invalidate_caches_for(["get-inbox", "get-projects", "get-tasks"])

        result = f"Converted '{project_title}' to project."
        if first_action:
            result += f"\nFirst action: {first_action}"
        else:
            result += "\n\n**Warning:** Project has no next action. GTD requires every project to have a clear next step. Use schedule-task to add one."

        return result

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error converting to project: {str(e)}")
        _error_result(f"Error converting to project: {str(e)}")


# --- GTD ORGANIZE STAGE ---


@mcp.tool(
    name="schedule-task", annotations=TOOL_ANNOTATIONS["schedule-task"], timeout=30
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
) -> str:
    """Create a task with specific scheduling and organization.

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

        # Build URL
        url = add_todo(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            checklist_items=checklist,
            list_title=project,  # project name
        )

        success = execute_url(url)
        if not success:
            _error_result("Failed to schedule task")

        invalidate_caches_for(["get-tasks", "get-today", "get-upcoming", "get-anytime"])

        result = f"Scheduled: {title}\n"
        result += f"- When: {when}\n"
        if deadline:
            result += f"- Deadline: {deadline}\n"
        if project:
            result += f"- Project: {project}\n"
        if context:
            result += f"- Context: {', '.join(context)}\n"

        return result

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error scheduling task: {str(e)}")
        _error_result(f"Error scheduling task: {str(e)}")


@mcp.tool(
    name="delegate-task", annotations=TOOL_ANNOTATIONS["delegate-task"], timeout=30
)
async def delegate_task(
    task_id: str,
    delegated_to: str,
    follow_up_date: Optional[str] = None,
    notes: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Delegate a task and track it as 'Waiting For'.

    GTD Stage: Organize
    Use when: You've handed off a task to someone else.

    This adds a 'waiting-for' tag, updates the title to show who you're
    waiting on, and sets an optional follow-up deadline.

    Args:
        task_id: UUID of the task to delegate
        delegated_to: Person's name you're waiting on
        follow_up_date: When to follow up (YYYY-MM-DD)
        notes: Notes about the delegation (e.g., "Emailed on Jan 20")
    """
    if ctx:
        await ctx.info(f"Delegating task to {delegated_to}...")

    try:
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

        result = f"Delegated to {delegated_to}: {original_title}\n"
        result += "- Tagged: waiting-for\n"
        if follow_up_date:
            result += f"- Follow up: {follow_up_date}\n"
        else:
            result += "- No follow-up date set. Will appear in weekly review.\n"

        return result

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error delegating task: {str(e)}")
        _error_result(f"Error delegating task: {str(e)}")


@mcp.tool(name="defer-task", annotations=TOOL_ANNOTATIONS["defer-task"], timeout=30)
async def defer_task(
    task_id: str,
    defer_to: str,
    reason: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Defer a task to a later time.

    GTD Stage: Organize

    IMPORTANT - GTD distinguishes two types of deferral:
    - defer_to="someday" → Someday/Maybe list (indefinite incubation)
    - defer_to=date → Tickler file (will reappear on that date)

    Args:
        task_id: UUID of the task to defer
        defer_to: When - "someday", "tomorrow", "next_week", or YYYY-MM-DD
        reason: Why you're deferring (appended to notes)
    """
    if ctx:
        await ctx.info(f"Deferring task to {defer_to}...")

    try:
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

            next_monday = date.today() + timedelta(days=(7 - date.today().weekday()))
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

        invalidate_caches_for(["get-tasks", "get-today", "get-upcoming", "get-someday"])

        if defer_to == "someday":
            return (
                "Moved to Someday/Maybe for incubation.\n\n"
                "This item will appear in your weekly review for reconsideration."
            )
        else:
            return f"Deferred to {when_value}. Task will reappear on that date."

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error deferring task: {str(e)}")
        _error_result(f"Error deferring task: {str(e)}")


@mcp.tool(name="plan-project", annotations=TOOL_ANNOTATIONS["plan-project"], timeout=30)
async def plan_project(
    title: str,
    tasks: List[Dict[str, Any]],
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    area: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Create a project with initial tasks atomically.

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

        result = f"Created project: {title}\n"
        result += f"- {len(tasks)} tasks added\n"
        if deadline:
            result += f"- Deadline: {deadline}\n"

        if not has_next_action:
            result += "\n**Warning:** No immediate next action. GTD recommends at least one task with when='anytime' to make progress."

        return result

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        _error_result(f"Error creating project: {str(e)}")


@mcp.tool(name="modify-task", annotations=TOOL_ANNOTATIONS["modify-task"], timeout=30)
async def modify_task(
    task_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    add_notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    add_tags: Optional[List[str]] = None,
    checklist: Optional[List[str]] = None,
    add_checklist: Optional[List[str]] = None,
    ctx: Context = None,
) -> str:
    """General task modification for updates not covered by specific tools.

    GTD Stage: Organize
    Instead use: complete-task for completing, defer-task for rescheduling,
                 delegate-task for delegation.

    Args:
        task_id: UUID of the task to update
        title: New title (replaces existing)
        notes: New notes (replaces existing)
        add_notes: Notes to append (preserves existing)
        when: New schedule
        deadline: New deadline
        tags: New tags (replaces existing)
        add_tags: Tags to add (preserves existing)
        checklist: New checklist items (replaces existing)
        add_checklist: Checklist items to append (preserves existing)
    """
    if ctx:
        await ctx.info("Updating task...")

    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Ensure tags exist
        all_tags = (tags or []) + (add_tags or [])
        if all_tags:
            ensure_tags_exist(all_tags)

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
        )

        success = execute_url(url)
        if not success:
            _error_result("Failed to update task")

        invalidate_caches_for(["get-tasks"])

        return "Task updated successfully."

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}")
        _error_result(f"Error updating task: {str(e)}")


# --- GTD REFLECT STAGE ---


@mcp.tool(name="daily-review", annotations=TOOL_ANNOTATIONS["daily-review"], timeout=5)
async def daily_review(ctx: Context = None) -> str:
    """Get a daily overview following GTD daily review.

    GTD Stage: Reflect
    Use when: Start of day, or asking "what do I need to do today?"

    Returns:
    - Today's scheduled tasks (hard landscape)
    - Overdue tasks requiring attention
    - Inbox count (items awaiting clarification)
    """
    if ctx:
        await ctx.info("Running daily review...")

    try:
        from datetime import date

        today_str = date.today().isoformat()

        # Get data
        today_tasks = things.today()
        inbox = things.inbox()

        # Find overdue tasks
        all_todos = things.todos(status="incomplete")
        overdue = [
            t for t in all_todos if t.get("deadline") and t.get("deadline") < today_str
        ]

        # Build summary
        output = "# Daily Review\n\n"
        output += f"**Summary:** {len(today_tasks or [])} tasks today"
        if overdue:
            output += f", **{len(overdue)} overdue**"
        if inbox:
            output += f", {len(inbox)} in inbox"
        output += "\n\n"

        # Overdue section (priority)
        if overdue:
            output += "## ⚠️ Overdue\n\n"
            for t in overdue[:5]:
                output += f"- **{t.get('title')}** (deadline: {t.get('deadline')})\n"
            if len(overdue) > 5:
                output += f"- ...and {len(overdue) - 5} more\n"
            output += "\n"

        # Today's tasks
        output += "## Today's Tasks\n\n"
        if today_tasks:
            for t in today_tasks:
                deadline_note = (
                    f" [due: {t.get('deadline')}]" if t.get("deadline") else ""
                )
                output += f"- {t.get('title')}{deadline_note}\n"
        else:
            output += (
                "No tasks scheduled for today. Check anytime tasks or process inbox.\n"
            )
        output += "\n"

        # Inbox status
        if inbox:
            output += f"## Inbox ({len(inbox)} items)\n\n"
            output += "Use process-inbox to clarify these items.\n"
            for t in inbox[:3]:
                output += f"- {t.get('title')}\n"
            if len(inbox) > 3:
                output += f"- ...and {len(inbox) - 3} more\n"

        return output

    except Exception as e:
        logger.error(f"Error in daily review: {str(e)}")
        _error_result(f"Error running daily review: {str(e)}")


@mcp.tool(
    name="weekly-review", annotations=TOOL_ANNOTATIONS["weekly-review"], timeout=10
)
async def weekly_review(ctx: Context = None) -> str:
    """Comprehensive GTD weekly review.

    GTD Stage: Reflect
    David Allen calls this the "critical factor for success."

    Returns:
    - Stalled projects (no next action)
    - Waiting-for items (especially overdue follow-ups)
    - Someday/Maybe items to reconsider
    - Completed this week (celebration!)
    - Inbox status
    """
    if ctx:
        await ctx.info("Running weekly review...")

    try:
        from datetime import date

        today = date.today()
        today_str = today.isoformat()

        output = "# Weekly Review\n\n"

        # 1. Inbox status
        inbox = things.inbox()
        if inbox:
            output += f"## 📥 Inbox: {len(inbox)} items\n"
            output += "**GTD:** Process to zero before finishing review.\n\n"
        else:
            output += "## ✅ Inbox: Clear\n\n"

        # 2. Stalled projects
        projects = things.projects()
        stalled = []
        for project in projects or []:
            if project.get("status") != "incomplete":
                continue
            # Get tasks for this project
            tasks = things.todos(project=project.get("uuid"), status="incomplete")
            # Check if any task is available (anytime or today)
            available = [
                t
                for t in (tasks or [])
                if t.get("start") in (None, "Anytime", "Today")
                or t.get("start_date") is None
                or t.get("start_date") == today_str
            ]
            if not available:
                stalled.append(project)

        if stalled:
            output += f"## ⚠️ Stalled Projects: {len(stalled)}\n"
            output += "These projects have no available next action:\n\n"
            for p in stalled[:5]:
                output += (
                    f"- **{p.get('title')}** - Add a next action to make progress\n"
                )
            if len(stalled) > 5:
                output += f"- ...and {len(stalled) - 5} more\n"
            output += "\n"
        else:
            output += "## ✅ All Projects Have Next Actions\n\n"

        # 3. Waiting-for items
        waiting = things.todos(tag="waiting-for", status="incomplete")
        if waiting:
            output += f"## ⏳ Waiting For: {len(waiting)} items\n\n"
            overdue_waiting = [
                w
                for w in waiting
                if w.get("deadline") and w.get("deadline") < today_str
            ]
            if overdue_waiting:
                output += "**Overdue follow-ups:**\n"
                for w in overdue_waiting[:3]:
                    output += f"- {w.get('title')} (was due: {w.get('deadline')})\n"
                output += "\n"
            output += "Review and follow up on delegated items.\n\n"

        # 4. Someday/Maybe review
        someday = things.someday()
        if someday:
            output += f"## 💭 Someday/Maybe: {len(someday)} items\n"
            output += "Consider: Should any of these become active?\n\n"
            for s in (someday or [])[:3]:
                output += f"- {s.get('title')}\n"
            if len(someday or []) > 3:
                output += f"- ...and {len(someday) - 3} more\n"
            output += "\n"

        # 5. Completed this week
        completed = things.last("7d", status="completed")
        if completed:
            output += f"## 🎉 Completed This Week: {len(completed)} items\n"
            output += "Celebrate your accomplishments!\n\n"
            for c in (completed or [])[:5]:
                output += f"- ~~{c.get('title')}~~\n"
            if len(completed) > 5:
                output += f"- ...and {len(completed) - 5} more\n"

        return output

    except Exception as e:
        logger.error(f"Error in weekly review: {str(e)}")
        _error_result(f"Error running weekly review: {str(e)}")


# --- UTILITY TOOLS ---


@mcp.tool(name="search-tasks", annotations=TOOL_ANNOTATIONS["search-tasks"], timeout=5)
async def search_tasks(
    query: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    area: Optional[str] = None,
    deadline: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """Search for tasks by keyword or filters.

    GTD Stage: Utility
    Use when: Looking for a specific task or filtering by criteria.

    Args:
        query: Search text (matches title and notes)
        status: Filter by status - incomplete, completed, canceled
        tag: Filter by tag (context)
        area: Filter by area
        deadline: Filter by deadline date
    """
    if ctx:
        await ctx.info("Searching tasks...")

    try:
        # Build search parameters
        kwargs = {}
        if status:
            kwargs["status"] = status
        if tag:
            kwargs["tag"] = tag
        if area:
            kwargs["area"] = area
        if deadline:
            kwargs["deadline"] = deadline

        # Get tasks
        if query:
            todos = things.search(query)
        elif kwargs:
            todos = things.todos(**kwargs)
        else:
            _error_result(
                "Provide query or at least one filter (status, tag, area, deadline)"
            )

        if not todos:
            return "No tasks found matching your criteria."

        # Format results
        summary = f"**Found {len(todos)} task{'s' if len(todos) != 1 else ''}**\n\n"
        formatted_todos = [format_todo(todo) for todo in todos[:20]]

        result = summary + "\n\n---\n\n".join(formatted_todos)
        if len(todos) > 20:
            result += f"\n\n*...and {len(todos) - 20} more results*"

        return result

    except Exception as e:
        logger.error(f"Error searching tasks: {str(e)}")
        _error_result(f"Error searching tasks: {str(e)}")


@mcp.tool(name="show-in-app", annotations=TOOL_ANNOTATIONS["show-in-app"], timeout=10)
async def show_in_app(
    id: str,
    ctx: Context = None,
) -> str:
    """Open a specific item or list in the Things app.

    Args:
        id: Item UUID, or list name: inbox, today, upcoming, anytime, someday, logbook,
            tomorrow, deadlines, repeating, all-projects, logged-projects
    """
    if ctx:
        await ctx.info(f"Opening '{id}' in Things...")

    try:
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        result = show(id=id)
        if not result:
            _error_result(f"Failed to open '{id}'")

        return f"Opened '{id}' in Things"

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error showing in app: {str(e)}")
        _error_result(f"Error showing in app: {str(e)}")


# =============================================================================
# DEPRECATED TOOLS (kept for backward compatibility)
# =============================================================================

# LIST VIEWS


@mcp.tool(name="get-inbox", annotations=TOOL_ANNOTATIONS["get-inbox"], timeout=5)
async def get_inbox(ctx: Context = None) -> str:
    """Get todos from Inbox"""
    import time

    start_time = time.time()
    log_operation_start("get-inbox")
    if ctx:
        await ctx.info("Fetching inbox items...")

    try:
        todos = things.inbox()

        if not todos:
            log_operation_end("get-inbox", True, time.time() - start_time, count=0)
            return "No items found in Inbox"

        formatted_todos = [format_todo(todo) for todo in todos]
        log_operation_end("get-inbox", True, time.time() - start_time, count=len(todos))
        return "\n\n---\n\n".join(formatted_todos)
    except Exception as e:
        log_operation_end("get-inbox", False, time.time() - start_time, error=str(e))
        raise


@mcp.tool(name="get-today", annotations=TOOL_ANNOTATIONS["get-today"], timeout=5)
@cached(ttl=CACHE_TTL.get("today", 30))
async def get_today(ctx: Context = None) -> str:
    """Get todos due today"""
    import time

    start_time = time.time()
    log_operation_start("get-today")
    if ctx:
        await ctx.info("Fetching today's items...")

    try:
        todos = things.today()

        if not todos:
            log_operation_end("get-today", True, time.time() - start_time, count=0)
            return "No items due today"

        formatted_todos = [format_todo(todo) for todo in todos]
        log_operation_end("get-today", True, time.time() - start_time, count=len(todos))
        return "\n\n---\n\n".join(formatted_todos)
    except Exception as e:
        log_operation_end("get-today", False, time.time() - start_time, error=str(e))
        raise


@mcp.tool(name="get-upcoming", annotations=TOOL_ANNOTATIONS["get-upcoming"], timeout=5)
async def get_upcoming(ctx: Context = None) -> str:
    """Get upcoming todos"""
    if ctx:
        await ctx.info("Fetching upcoming items...")
    todos = things.upcoming()

    if not todos:
        return "No upcoming items"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(name="get-anytime", annotations=TOOL_ANNOTATIONS["get-anytime"], timeout=5)
async def get_anytime(ctx: Context = None) -> str:
    """Get todos from Anytime list"""
    if ctx:
        await ctx.info("Fetching Anytime items...")
    todos = things.anytime()

    if not todos:
        return "No items in Anytime list"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(name="get-someday", annotations=TOOL_ANNOTATIONS["get-someday"], timeout=5)
async def get_someday(ctx: Context = None) -> str:
    """Get todos from Someday list"""
    if ctx:
        await ctx.info("Fetching Someday items...")
    todos = things.someday()

    if not todos:
        return "No items in Someday list"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(name="get-logbook", annotations=TOOL_ANNOTATIONS["get-logbook"], timeout=5)
async def get_logbook(period: str = "7d", limit: int = 50, ctx: Context = None) -> str:
    """
    Get completed todos from Logbook, defaults to last 7 days

    Args:
        period: Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'
        limit: Maximum number of entries to return. Defaults to 50
    """
    if ctx:
        await ctx.info(f"Fetching logbook items for last {period}...")
    todos = things.last(period, status="completed")

    if not todos:
        return "No completed items found"

    if todos and len(todos) > limit:
        todos = todos[:limit]

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(name="get-trash", annotations=TOOL_ANNOTATIONS["get-trash"], timeout=5)
async def get_trash(ctx: Context = None) -> str:
    """Get trashed todos"""
    if ctx:
        await ctx.info("Fetching trash items...")
    todos = things.trash()

    if not todos:
        return "No items in trash"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


# BASIC TODO OPERATIONS


@mcp.tool(name="get-todos", annotations=TOOL_ANNOTATIONS["get-todos"], timeout=5)
async def get_todos(
    project_uuid: Optional[str] = None, include_items: bool = True, ctx: Context = None
) -> str:
    """
    Get todos from Things, optionally filtered by project

    Args:
        project_uuid: Optional UUID of a specific project to get todos from
        include_items: Include checklist items
    """
    if ctx:
        await ctx.info("Fetching todos...")
    if project_uuid:
        project = things.get(project_uuid)
        if not project or project.get("type") != "project":
            _error_result(f"Invalid project UUID '{project_uuid}'")

    todos = things.todos(project=project_uuid, start=None)

    if not todos:
        return "No todos found"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(name="get-projects", annotations=TOOL_ANNOTATIONS["get-projects"], timeout=5)
async def get_projects(include_items: bool = False, ctx: Context = None) -> str:
    """
    Get all projects from Things

    Args:
        include_items: Include tasks within projects
    """
    if ctx:
        await ctx.info("Fetching projects...")
    projects = things.projects()

    if not projects:
        return "No projects found"

    formatted_projects = [
        format_project(project, include_items) for project in projects
    ]
    return "\n\n---\n\n".join(formatted_projects)


@mcp.tool(name="get-areas", annotations=TOOL_ANNOTATIONS["get-areas"], timeout=5)
async def get_areas(include_items: bool = False, ctx: Context = None) -> str:
    """
    Get all areas from Things

    Args:
        include_items: Include projects and tasks within areas
    """
    if ctx:
        await ctx.info("Fetching areas...")
    areas = things.areas()

    if not areas:
        return "No areas found"

    formatted_areas = [format_area(area, include_items) for area in areas]
    return "\n\n---\n\n".join(formatted_areas)


# TAG OPERATIONS


@mcp.tool(name="get-tags", annotations=TOOL_ANNOTATIONS["get-tags"], timeout=5)
async def get_tags(include_items: bool = False, ctx: Context = None) -> str:
    """
    Get all tags

    Args:
        include_items: Include items tagged with each tag
    """
    if ctx:
        await ctx.info("Fetching tags...")
    tags = things.tags()

    if not tags:
        return "No tags found"

    formatted_tags = [format_tag(tag, include_items) for tag in tags]
    return "\n\n---\n\n".join(formatted_tags)


@mcp.tool(
    name="get-tagged-items", annotations=TOOL_ANNOTATIONS["get-tagged-items"], timeout=5
)
async def get_tagged_items(tag: str, ctx: Context = None) -> str:
    """
    Get items with a specific tag

    Args:
        tag: Tag title to filter by
    """
    if ctx:
        await ctx.info(f"Fetching items with tag '{tag}'...")
    todos = things.todos(tag=tag)

    if not todos:
        return f"No items found with tag '{tag}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


# SEARCH OPERATIONS


@mcp.tool(name="search-todos", annotations=TOOL_ANNOTATIONS["search-todos"], timeout=5)
async def search_todos(query: str, ctx: Context = None) -> str:
    """
    Search todos by title or notes

    Args:
        query: Search term to look for in todo titles and notes
    """
    if ctx:
        await ctx.info(f"Searching for '{query}'...")
    todos = things.search(query)

    if not todos:
        return f"No todos found matching '{query}'"

    formatted_todos = [format_todo(todo) for todo in todos]
    return "\n\n---\n\n".join(formatted_todos)


@mcp.tool(
    name="search-advanced", annotations=TOOL_ANNOTATIONS["search-advanced"], timeout=5
)
async def search_advanced(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    deadline: Optional[str] = None,
    tag: Optional[str] = None,
    area: Optional[str] = None,
    type: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """
    Advanced todo search with multiple filters

    Args:
        status: Filter by todo status (incomplete/completed/canceled)
        start_date: Filter by start date (YYYY-MM-DD)
        deadline: Filter by deadline (YYYY-MM-DD)
        tag: Filter by tag
        area: Filter by area UUID
        type: Filter by item type (to-do/project/heading)
    """
    if ctx:
        await ctx.info("Running advanced search...")
    # Build filter parameters
    kwargs = {}

    # Add filters that are provided
    if status:
        kwargs["status"] = status
    if deadline:
        kwargs["deadline"] = deadline
    if start_date:
        kwargs["start"] = start_date
    if tag:
        kwargs["tag"] = tag
    if area:
        kwargs["area"] = area
    if type:
        kwargs["type"] = type

    # Execute search with applicable filters
    try:
        todos = things.todos(**kwargs)

        if not todos:
            return "No items found matching your search criteria"

        formatted_todos = [format_todo(todo) for todo in todos]
        return "\n\n---\n\n".join(formatted_todos)
    except Exception as e:
        _error_result(f"Error in advanced search: {str(e)}")


# MODIFICATION OPERATIONS


@mcp.tool(name="add-todo", annotations=TOOL_ANNOTATIONS["add-todo"], timeout=30)
async def add_task(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    checklist_items: Optional[List[str]] = None,
    list_id: Optional[str] = None,
    list_title: Optional[str] = None,
    heading: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """
    Create a new todo in Things.

    Args:
        title: Title of the todo
        notes: Notes for the todo
        when: When to schedule the todo (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD)
        deadline: Deadline for the todo (YYYY-MM-DD)
        tags: Tags to apply to the todo. Missing tags will be created automatically.
        checklist_items: Checklist items to add
        list_id: ID of project/area to add to
        list_title: Title of project/area to add to
        heading: Heading to add under
    """
    try:
        if ctx:
            await ctx.info("Creating todo...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Ensure tags exist before using them
        if tags:
            ensure_tags_exist(tags)

        # Build the add_todo URL command and execute it
        url = add_todo(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            checklist_items=checklist_items,
            list_id=list_id,
            list_title=list_title,
            heading=heading,
        )

        # Log the generated URL before executing
        logger.debug(f"Add todo URL: {url}")

        success = execute_url(url)

        if not success:
            _error_result("Failed to create todo")

        # Invalidate relevant caches after creating a todo
        invalidate_caches_for(["get-inbox", "get-today", "get-upcoming", "get-todos"])

        if ctx:
            await ctx.info("Todo created successfully")
        return f"Successfully created todo: {title}"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error creating todo: {str(e)}")
        _error_result(f"Error creating todo: {str(e)}")


@mcp.tool(name="add-project", annotations=TOOL_ANNOTATIONS["add-project"], timeout=30)
async def add_new_project(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    area_id: Optional[str] = None,
    area_title: Optional[str] = None,
    todos: Optional[List[str]] = None,
    ctx: Context = None,
) -> str:
    """
    Create a new project in Things

    Args:
        title: Title of the project
        notes: Notes for the project
        when: When to schedule the project
        deadline: Deadline for the project
        tags: Tags to apply to the project
        area_id: ID of area to add to
        area_title: Title of area to add to
        todos: Initial todos to create in the project
    """
    try:
        if ctx:
            await ctx.info("Creating project...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Build the add_project URL command and execute it
        url = add_project(
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            area_id=area_id,
            area_title=area_title,
            todos=todos,
        )

        # Log the generated URL before executing
        logger.debug(f"Add project URL: {url}")

        success = execute_url(url)

        if not success:
            _error_result("Failed to create project")

        if ctx:
            await ctx.info("Project created successfully")
        return f"Successfully created project: {title}"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        _error_result(f"Error creating project: {str(e)}")


@mcp.tool(name="update-todo", annotations=TOOL_ANNOTATIONS["update-todo"], timeout=30)
async def update_task(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
    ctx: Context = None,
) -> str:
    """
    Update an existing todo in Things.

    Args:
        id: ID of the todo to update
        title: New title
        notes: New notes
        when: New schedule
        deadline: New deadline
        tags: New tags. Missing tags will be created automatically.
        completed: Mark as completed
        canceled: Mark as canceled
    """
    try:
        if ctx:
            await ctx.info("Updating todo...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Ensure tags exist before using them
        if tags:
            ensure_tags_exist(tags)

        # Build the update_todo URL command and execute it
        url = update_todo(
            id=id,
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            completed=completed,
            canceled=canceled,
        )

        logger.debug(f"Update todo URL: {url}")

        success = execute_url(url)

        if not success:
            _error_result("Failed to update todo")

        if ctx:
            await ctx.info("Todo updated successfully")
        return f"Successfully updated todo with ID: {id}"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error updating todo: {str(e)}")
        _error_result(f"Error updating todo: {str(e)}")


@mcp.tool(
    name="update-project", annotations=TOOL_ANNOTATIONS["update-project"], timeout=30
)
async def update_existing_project(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[List[str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
    ctx: Context = None,
) -> str:
    """
    Update an existing project in Things

    Args:
        id: ID of the project to update
        title: New title
        notes: New notes
        when: New schedule
        deadline: New deadline
        tags: New tags
        completed: Mark as completed
        canceled: Mark as canceled
    """
    try:
        if ctx:
            await ctx.info("Updating project...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Build the update_project URL command and execute it
        url = update_project(
            id=id,
            title=title,
            notes=notes,
            when=when,
            deadline=deadline,
            tags=tags,
            completed=completed,
            canceled=canceled,
        )

        # Log the generated URL before executing
        logger.debug(f"Update project URL: {url}")

        success = execute_url(url)

        if not success:
            _error_result("Failed to update project")

        if ctx:
            await ctx.info("Project updated successfully")
        return f"Successfully updated project with ID: {id}"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        _error_result(f"Error updating project: {str(e)}")


@mcp.tool(name="show-item", annotations=TOOL_ANNOTATIONS["show-item"], timeout=10)
async def show_item(
    id: str,
    query: Optional[str] = None,
    filter_tags: Optional[List[str]] = None,
    ctx: Context = None,
) -> str:
    """
    Show a specific item or list in Things

    Args:
        id: ID of item to show, or one of: inbox, today, upcoming, anytime, someday, logbook
        query: Optional query to filter by
        filter_tags: Optional tags to filter by
    """
    try:
        if ctx:
            await ctx.info(f"Opening '{id}' in Things...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Execute the show URL command
        result = show(id=id, query=query, filter_tags=filter_tags)

        if not result:
            _error_result(f"Failed to show item/list '{id}'")

        return f"Successfully opened '{id}' in Things"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error showing item: {str(e)}")
        _error_result(f"Error showing item: {str(e)}")


@mcp.tool(name="search-items", annotations=TOOL_ANNOTATIONS["search-items"], timeout=10)
async def search_all_items(query: str, ctx: Context = None) -> str:
    """
    Search for items in Things

    Args:
        query: Search query
    """
    try:
        if ctx:
            await ctx.info(f"Searching for '{query}' in Things...")
        # Ensure Things app is running
        if not app_state.update_app_state():
            if not launch_things():
                _error_result("Unable to launch Things app")

        # Execute the search URL command
        result = search(query=query)

        if not result:
            _error_result(f"Failed to search for '{query}'")

        return f"Successfully searched for '{query}' in Things"
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error searching: {str(e)}")
        _error_result(f"Error searching: {str(e)}")


@mcp.tool(name="get-recent", annotations=TOOL_ANNOTATIONS["get-recent"], timeout=5)
async def get_recent(period: str, ctx: Context = None) -> str:
    """
    Get recently created items

    Args:
        period: Time period (e.g., '3d', '1w', '2m', '1y')
    """
    try:
        if ctx:
            await ctx.info(f"Fetching recent items from last {period}...")
        # Check if period format is valid
        if not period or not any(
            period.endswith(unit) for unit in ["d", "w", "m", "y"]
        ):
            _error_result("Period must be in format '3d', '1w', '2m', '1y'")

        # Get recent items
        items = things.last(period)

        if not items:
            return f"No items found in the last {period}"

        formatted_items = []
        for item in items:
            if item.get("type") == "to-do":
                formatted_items.append(format_todo(item))
            elif item.get("type") == "project":
                formatted_items.append(format_project(item, include_items=False))

        return "\n\n---\n\n".join(formatted_items)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error getting recent items: {str(e)}")
        _error_result(f"Error getting recent items: {str(e)}")


@mcp.tool(
    name="get-cache-stats", annotations=TOOL_ANNOTATIONS["get-cache-stats"], timeout=5
)
async def get_cache_statistics(ctx: Context = None) -> str:
    """Get cache performance statistics"""
    if ctx:
        await ctx.info("Fetching cache statistics...")
    stats = get_cache_stats()

    return f"""Cache Statistics:
- Total entries: {stats["entries"]}
- Cache hits: {stats["hits"]}
- Cache misses: {stats["misses"]}
- Hit rate: {stats["hit_rate"]}
- Total requests: {stats["total_requests"]}"""


def _flatten_anyof_for_n8n(schema: dict) -> dict:
    """Flatten anyOf constructs in JSON Schema for n8n compatibility.

    n8n's MCP client doesn't handle anyOf properly (causes 'Cannot read properties
    of undefined' errors). This function transforms:
      {"anyOf": [{"type": "array", "items": {...}}, {"type": "null"}]}
    into:
      {"type": "array", "items": {...}}

    The null option is dropped since n8n handles missing/optional values differently.
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if key == "anyOf" and isinstance(value, list):
            # Find the non-null type in anyOf
            non_null_types = [t for t in value if t.get("type") != "null"]
            if len(non_null_types) == 1:
                # Flatten: merge the non-null type into the parent
                flattened = _flatten_anyof_for_n8n(non_null_types[0])
                result.update(flattened)
            else:
                # Multiple non-null types, keep anyOf but recurse
                result[key] = [_flatten_anyof_for_n8n(t) for t in value]
        elif key == "properties" and isinstance(value, dict):
            # Recurse into properties
            result[key] = {k: _flatten_anyof_for_n8n(v) for k, v in value.items()}
        elif isinstance(value, dict):
            result[key] = _flatten_anyof_for_n8n(value)
        elif isinstance(value, list):
            result[key] = [
                _flatten_anyof_for_n8n(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def _patch_tool_serialization_for_n8n():
    """Patch tool serialization to ensure inputSchema compatibility with n8n.

    n8n's MCP client doesn't handle 'anyOf' constructs in JSON Schema properly,
    causing "Cannot read properties of undefined (reading 'inputType')" errors.

    This patches the low-level request handler for ListToolsRequest to flatten
    anyOf constructs (used by Pydantic for Optional types) before returning
    tools to clients.

    Set THINGS_MCP_DEBUG_SCHEMA=1 to log full tool schemas for debugging.
    """
    import os
    import json
    import mcp.types as mcp_types

    debug_schema = os.environ.get("THINGS_MCP_DEBUG_SCHEMA", "").lower() in (
        "1",
        "true",
        "yes",
    )

    try:
        # Patch the low-level request handler registered with the MCP server
        # Note: 'mcp' here is the global FastMCP instance, not the mcp module
        request_handlers = mcp._mcp_server.request_handlers
        original_handler = request_handlers[mcp_types.ListToolsRequest]

        async def patched_list_tools_handler(request):
            logger.info(
                "ListToolsRequest handler - applying n8n schema compatibility patches"
            )
            result = await original_handler(request)
            # Result is ServerResult with root=ListToolsResult
            tools = result.root.tools
            # Transform each tool's inputSchema to flatten anyOf
            for tool in tools:
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' BEFORE flattening: {json.dumps(tool.inputSchema, indent=2)}"
                        )
                    # inputSchema is a dict, flatten it
                    flattened = _flatten_anyof_for_n8n(tool.inputSchema)
                    # Modify the dict in place
                    if isinstance(tool.inputSchema, dict):
                        tool.inputSchema.clear()
                        tool.inputSchema.update(flattened)
                    if debug_schema:
                        logger.info(
                            f"Tool '{tool.name}' AFTER flattening: {json.dumps(tool.inputSchema, indent=2)}"
                        )
            logger.info(f"Processed {len(tools)} tools with schema flattening")
            return result

        request_handlers[mcp_types.ListToolsRequest] = patched_list_tools_handler
        logger.info("Patched ListToolsRequest handler for n8n anyOf compatibility")
    except Exception as e:
        logger.warning(
            f"Could not patch ListToolsRequest handler for n8n compatibility: {e}"
        )


# Main entry point
def run_things_mcp_server():
    """Run the Things MCP server"""
    import signal
    import sys

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    host = get_binding_host()
    if host == DEFAULT_HOST:
        logger.info(
            "FastMCP will bind to %s (set %s=0.0.0.0 to allow remote connections)",
            DEFAULT_HOST,
            HOST_ENV_VAR,
        )
    else:
        logger.info(
            "FastMCP binding override detected: %s=%s",
            HOST_ENV_VAR,
            host,
        )

    # Ensure tool schema compatibility for n8n and other clients
    _patch_tool_serialization_for_n8n()

    # Check if Things app is available
    if not app_state.update_app_state():
        logger.warning(
            "Things app is not running at startup. MCP will attempt to launch it when needed."
        )
        try:
            # Try to launch Things
            if launch_things():
                logger.info("Successfully launched Things app")
            else:
                logger.error("Unable to launch Things app. Some operations may fail.")
        except Exception as e:
            logger.error(f"Error launching Things app: {str(e)}")
    else:
        logger.info("Things app is running and ready for operations")

    logger.info("Press Ctrl+C to stop the server")

    # Run the MCP server with HTTP transport
    mcp.run(
        transport="streamable-http",
        host=get_binding_host(),
        port=get_binding_port(),
    )


if __name__ == "__main__":
    run_things_mcp_server()
