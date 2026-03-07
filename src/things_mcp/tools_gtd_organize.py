"""GTD Organize Tools: schedule, delegate, defer, plan, modify.

These tools handle the "Organize" stage of GTD - putting things where they belong.
"""

from typing import Optional, List, Dict, Any

import things
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

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


def _resolve_list_id(name_or_uuid: str, list_type: str) -> str:
    """Resolve a project/area name or UUID to a UUID.

    Args:
        name_or_uuid: Project/area name or UUID
        list_type: "project" or "area"

    Returns:
        UUID string

    Raises:
        ToolError if not found or ambiguous
    """
    # If it looks like a UUID (long alphanumeric), try direct lookup first
    item = things.get(name_or_uuid)
    if item:
        return name_or_uuid

    # Search by name
    if list_type == "project":
        items = things.projects()
    else:
        items = things.areas()

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


def register_gtd_organize_tools(mcp: FastMCP):
    """Register GTD Organize stage tools with the MCP server."""

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

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-upcoming", "get-anytime"]
            )

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
        - defer_to="someday" -> Someday/Maybe list (indefinite incubation)
        - defer_to=date -> Tickler file (will reappear on that date)

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

    @mcp.tool(
        name="plan-project", annotations=TOOL_ANNOTATIONS["plan-project"], timeout=30
    )
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

    @mcp.tool(
        name="modify-task", annotations=TOOL_ANNOTATIONS["modify-task"], timeout=30
    )
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
        project: Optional[str] = None,
        area: Optional[str] = None,
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
            project: Project name or UUID to move task to
            area: Area name or UUID to move task to
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

            # Resolve project/area name to UUID if needed
            list_id = None
            if project:
                list_id = _resolve_list_id(project, "project")
            elif area:
                list_id = _resolve_list_id(area, "area")

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
            )

            success = execute_url(url)
            if not success:
                _error_result("Failed to update task")

            invalidate_caches_for(["get-tasks", "get-projects"])

            result = "Task updated successfully."
            if project:
                result += f" Moved to project: {project}"
            elif area:
                result += f" Moved to area: {area}"

            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}")
            _error_result(f"Error updating task: {str(e)}")
