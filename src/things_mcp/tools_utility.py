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
from .triage_tracker import triage_tracker

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

    @mcp.tool(
        name="triage-insights",
        annotations=TOOL_ANNOTATIONS["triage-insights"],
        timeout=5,
    )
    async def triage_insights(
        days: int = 7,
        category: Optional[str] = None,
        action: Optional[str] = None,
        show_trends: bool = False,
        ctx: Context = None,
    ) -> str:
        """Get insights into your inbox triage patterns.

        GTD Stage: Reflect
        Use when: Understanding capture and processing habits.

        Args:
            days: Number of days to analyze (default 7, 0 for all time)
            category: Filter by category (repo-research, vague-capture, client-person, etc.)
            action: Filter by action (completed, canceled, deferred-someday, delegated, etc.)
            show_trends: Show week-over-week trends (4 weeks)
        """
        if ctx:
            await ctx.info("Analyzing triage patterns...")

        try:
            summary = triage_tracker.get_summary(days=days)

            if summary["total"] == 0:
                period = f"last {days} days" if days > 0 else "all time"
                return (
                    f"No triage activity recorded in the {period}.\n\n"
                    "Triage actions are tracked automatically when you process "
                    "inbox items using complete-task, modify-task, defer-task, etc."
                )

            # Header
            period = f"last {days} days" if days > 0 else "all time"
            total = summary["total"]
            avg = summary["avg_per_day"]
            sessions = summary["sessions"]
            output = f"# Triage Insights ({period})\n\n"
            output += f"**{total} items triaged**"
            if sessions:
                output += f" across {sessions} session{'s' if sessions != 1 else ''}"
            output += f" | {avg}/day avg"
            if summary["busiest_day"]:
                output += f" | Busiest: {summary['busiest_day']}"
            output += "\n\n"

            # Action breakdown
            actions = summary["actions"]
            if actions:
                output += "## Actions\n\n"
                for act, count in sorted(actions.items(), key=lambda x: -x[1]):
                    pct = int(count / total * 100)
                    output += f"- {act}: {count} ({pct}%)\n"
                output += "\n"

            # Category breakdown
            categories = summary["categories"]
            if categories:
                output += "## Categories\n\n"
                for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                    pct = int(count / total * 100)
                    output += f"- {cat}: {count} ({pct}%)\n"
                output += "\n"

            # Actionable insights
            insights = []
            cancel_rate = summary["no_context_cancel_rate"]
            if cancel_rate > 0.3:
                pct = int(cancel_rate * 100)
                insights.append(
                    f"{pct}% of canceled items had no context at capture. "
                    "Adding notes when capturing could save triage time."
                )

            vague_count = categories.get("vague-capture", 0)
            if vague_count > 0 and total > 0:
                vague_pct = int(vague_count / total * 100)
                if vague_pct > 25:
                    insights.append(
                        f"{vague_pct}% of captures were vague (short title, no notes). "
                        "Try adding context when capturing to speed up future triage."
                    )

            delegated = actions.get("delegated", 0)
            if total > 10 and delegated == 0:
                insights.append(
                    "Nothing was delegated this period. "
                    "GTD recommends delegating tasks others can do."
                )

            if insights:
                output += "## Insights\n\n"
                for insight in insights:
                    output += f"- {insight}\n"
                output += "\n"

            # Trends
            if show_trends:
                trends = triage_tracker.get_trends(weeks=4)
                if trends:
                    output += "## Weekly Trends\n\n"
                    for i, week in enumerate(trends):
                        arrow = ""
                        if i < len(trends) - 1:
                            prev = trends[i + 1]["total"]
                            curr = week["total"]
                            if curr > prev:
                                arrow = " ^"
                            elif curr < prev:
                                arrow = " v"
                        output += f"- Week of {week['week_start']}: {week['total']} items{arrow}\n"

            output += "\nFull dashboard: http://localhost:8009/dashboard\n"

            return output

        except Exception as e:
            logger.error(f"Error in triage insights: {str(e)}")
            _error_result(f"Error analyzing triage patterns: {str(e)}")
