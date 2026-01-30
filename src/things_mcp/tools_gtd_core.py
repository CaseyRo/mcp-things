"""GTD Core Tools: Engage, Capture, and Clarify stages.

These tools form the "input" side of GTD:
- Engage: get-tasks, focus-mode, complete-task
- Capture: capture-task
- Clarify: process-inbox, convert-to-project
"""

from typing import Optional, List, Union

import things
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from .formatters import format_todo
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
from .tool_annotations import TOOL_ANNOTATIONS

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def register_gtd_core_tools(mcp: FastMCP):
    """Register GTD Engage, Capture, and Clarify tools with the MCP server."""

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
                    t
                    for t in today_tasks
                    if not t.get("deadline") and matches_filters(t)
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

                filter_str = (
                    ", ".join(filter_desc) if filter_desc else "current filters"
                )
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
                    t
                    for t in matches
                    if task_title.lower() in t.get("title", "").lower()
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
            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime"]
            )

            return "Task completed successfully. Keep up the momentum!"

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Error completing task: {str(e)}")
            _error_result(f"Error completing task: {str(e)}")

    # --- GTD CAPTURE STAGE ---

    @mcp.tool(
        name="capture-task", annotations=TOOL_ANNOTATIONS["capture-task"], timeout=30
    )
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
           - No -> Trash (delete), Someday (defer), or Reference (add notes)
        2. Is it a single action or multi-step project?
           - Project -> Use convert-to-project
        3. Can it be done in <2 minutes?
           - Yes -> Do it now!
           - No -> Delegate (delegate-task) or Defer (schedule-task)
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
            output += "   - No, trash it -> Use update-todo with canceled=true\n"
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
            project_deadline = task.get("deadline")

            # Get checklist items from the original task
            checklist_items = things.checklist_items(task_id)

            # Build tasks array for the project
            tasks = []
            if first_action:
                tasks.append({"title": first_action, "when": "anytime"})

            # Convert checklist items to project tasks (incomplete ones only)
            for item in checklist_items:
                if item.get("status") != "completed":
                    tasks.append({"title": item.get("title", ""), "when": "anytime"})

            # Use JSON API for atomic creation
            url = add_project_with_tasks(
                title=project_title,
                tasks=tasks,
                notes=project_notes,
                deadline=project_deadline,
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

            # Build result message
            result = f"Converted '{project_title}' to project."
            if project_deadline:
                result += f"\nDeadline: {project_deadline}"

            checklist_count = len(
                [i for i in checklist_items if i.get("status") != "completed"]
            )
            if first_action and checklist_count > 0:
                result += f"\nTasks: {first_action} + {checklist_count} from checklist"
            elif first_action:
                result += f"\nFirst action: {first_action}"
            elif checklist_count > 0:
                result += f"\nConverted {checklist_count} checklist items to tasks."
            else:
                result += "\n\n**Warning:** Project has no next action. GTD requires every project to have a clear next step. Use schedule-task to add one."

            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Error converting to project: {str(e)}")
            _error_result(f"Error converting to project: {str(e)}")
