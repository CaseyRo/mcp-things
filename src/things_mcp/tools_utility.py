"""Utility Tools: search, list projects/areas/tags, show in app, cache stats.

These tools support general operations not tied to a specific GTD stage.
"""

from typing import Optional

import things
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from .formatters import format_todo, format_project, format_area, format_tag
from .utils import app_state
from .url_scheme import show, launch_things
from .logging_config import get_logger
from .cache import get_cache_stats
from .tool_annotations import TOOL_ANNOTATIONS

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def register_utility_tools(mcp: FastMCP):
    """Register utility tools with the MCP server."""

    @mcp.tool(
        name="search-tasks", annotations=TOOL_ANNOTATIONS["search-tasks"], timeout=5
    )
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

    @mcp.tool(
        name="get-projects", annotations=TOOL_ANNOTATIONS["get-projects"], timeout=5
    )
    async def get_projects(include_items: bool = False, ctx: Context = None) -> str:
        """Get all projects from Things.

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
        """Get all areas from Things.

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

    @mcp.tool(name="get-tags", annotations=TOOL_ANNOTATIONS["get-tags"], timeout=5)
    async def get_tags(include_items: bool = False, ctx: Context = None) -> str:
        """Get all tags.

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
        name="show-in-app", annotations=TOOL_ANNOTATIONS["show-in-app"], timeout=10
    )
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

    @mcp.tool(
        name="get-cache-stats",
        annotations=TOOL_ANNOTATIONS["get-cache-stats"],
        timeout=5,
    )
    async def get_cache_statistics(ctx: Context = None) -> str:
        """Get cache performance statistics."""
        if ctx:
            await ctx.info("Fetching cache statistics...")
        stats = get_cache_stats()

        return f"""Cache Statistics:
- Total entries: {stats["entries"]}
- Cache hits: {stats["hits"]}
- Cache misses: {stats["misses"]}
- Hit rate: {stats["hit_rate"]}
- Total requests: {stats["total_requests"]}"""
