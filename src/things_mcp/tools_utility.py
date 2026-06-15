"""Utility Tools: search, list projects/areas/tags, show in app, cache stats.

These tools support general operations not tied to a specific GTD stage.

All tools in this module return ``ToolResult`` with a ``ToolEnvelope`` in
``structured_content`` and a backwards-compatible text block in ``content``.
See ``openspec/changes/structured-json-tool-output/`` for the contract.
"""

from typing import Optional

from . import reader as db
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult

from .formatters import (
    render_area,
    render_project,
    render_tag,
    render_todo,
    to_dict_area,
    to_dict_project,
    to_dict_tag,
    to_dict_todo,
)
from .models import (
    Area,
    CacheStats,
    Project,
    ShowInAppResult,
    Tag,
    Todo,
    ToolEnvelope,
    TriageActionStats,
    TriageInsights,
    output_schema_for,
)
from .tool_results import make_result
from .utils import app_state
from .url_scheme import show, launch_things
from .logging_config import get_logger
from .cache import get_cache_stats
from .tool_annotations import TOOL_ANNOTATIONS, tags_for
from .triage_tracker import triage_tracker
from .settings import get_dashboard_url
from .input_validation import validate_show_id
from .resolvers import resolve_item

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def register_utility_tools(mcp: FastMCP):
    """Register utility tools with the MCP server."""

    @mcp.tool(
        name="search-tasks",
        annotations=TOOL_ANNOTATIONS["search-tasks"],
        tags=tags_for("search-tasks"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[list[Todo]]),
    )
    async def search_tasks(
        query: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        area: Optional[str] = None,
        deadline: Optional[str] = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Search for tasks by keyword or filters.

        GTD Stage: Utility
        Use when: Looking for a specific task or filtering by criteria.
        Results are capped at `limit` (default 20). Increase limit to see more.

        Note on `area`: `area` filters by an *area of responsibility* (name or
        UUID). Things' built-in lists — Inbox, Today, Anytime, Someday, Upcoming,
        Logbook, Trash — are NOT areas. To list one of those, use
        get-tasks(view="inbox" | "today" | "anytime" | ...). Passing a list name
        like area="Inbox" is rejected with this guidance rather than silently
        returning empty (CDI-1255).

        Args:
            query: Search text (matches title and notes)
            status: Filter by status - incomplete, completed, canceled
            tag: Filter by tag (context)
            area: Filter by area of responsibility (name or UUID), NOT a built-in
                list. For Inbox/Today/Anytime/etc. use get-tasks(view=...).
            deadline: Filter by deadline date
            limit: Maximum results to return (default 20, max 200)
        """
        if ctx:
            await ctx.info("Searching tasks...")

        # Built-in Things lists are not areas. Reject area="Inbox" (and the other
        # list names) with a clear redirect instead of silently returning empty.
        # CDI-1255 secondary fix.
        _BUILTIN_LISTS = {
            "inbox": "inbox",
            "today": "today",
            "tomorrow": "tomorrow",
            "upcoming": "upcoming",
            "anytime": "anytime",
            "someday": "someday",
            "logbook": "logbook",
            "trash": "trash",
            "deadlines": "deadlines",
        }
        if area and area.strip().lower() in _BUILTIN_LISTS:
            view = _BUILTIN_LISTS[area.strip().lower()]
            _error_result(
                f"'{area}' is a built-in Things list, not an area. "
                f"Use get-tasks(view='{view}') to list its contents. "
                "The `area` filter is for areas of responsibility only."
            )

        try:
            kwargs = {}
            if status:
                kwargs["status"] = status
            if tag:
                kwargs["tag"] = tag
            if area:
                kwargs["area"] = area
            if deadline:
                kwargs["deadline"] = deadline

            if query:
                todos = db.search(query)
            elif kwargs:
                todos = db.todos(**kwargs)
            else:
                _error_result(
                    "Provide query or at least one filter (status, tag, area, deadline)"
                )

            if not todos:
                # CDI-1255: distinguish a genuine empty result from a possibly
                # stale index (something written but not yet flushed to SQLite).
                stale = db.index_stale()
                if stale:
                    msg = (
                        "No tasks found matching your criteria yet — a task was "
                        "captured very recently and Things may not have flushed it "
                        "to the read index. Retry in a moment."
                    )
                else:
                    msg = "No tasks found matching your criteria."
                return make_result(
                    data=[],
                    summary=msg,
                    text=msg,
                    meta={"index_stale": stale},
                )

            effective_limit = min(max(1, limit), 200)
            total_count = len(todos)
            shown = todos[:effective_limit]

            data = [to_dict_todo(t) for t in shown]
            summary = f"Found {total_count} task{'s' if total_count != 1 else ''}" + (
                f" (showing {effective_limit})" if total_count > effective_limit else ""
            )

            text_summary = (
                f"**Found {total_count} task{'s' if total_count != 1 else ''}**"
            )
            if total_count > effective_limit:
                text_summary += f" (showing {effective_limit})"
            text_summary += "\n\n"
            text_body = text_summary + "\n\n---\n\n".join(render_todo(t) for t in shown)
            if total_count > effective_limit:
                text_body += (
                    f"\n\n*...and {total_count - effective_limit} more results. "
                    "Use limit= to see more.*"
                )

            meta = {"total_count": total_count, "shown": len(shown)}
            if total_count > effective_limit:
                meta["truncated"] = True

            return make_result(data=data, summary=summary, meta=meta, text=text_body)

        except ToolError:
            raise
        except Exception:
            logger.error("Error searching tasks", exc_info=True)
            _error_result("Failed to search tasks. Check server logs for details.")

    @mcp.tool(
        name="get-projects",
        annotations=TOOL_ANNOTATIONS["get-projects"],
        tags=tags_for("get-projects"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[list[Project]]),
    )
    async def get_projects(
        include_items: bool = False, ctx: Context = None
    ) -> ToolResult:
        """[tasks-gtd] Get all projects from Things.

        Args:
            include_items: Include tasks within projects
        """
        if ctx:
            await ctx.info("Fetching projects...")
        projects = db.projects() or []

        if not projects:
            return make_result(
                data=[], summary="No projects found", text="No projects found"
            )

        data = [to_dict_project(p, include_items) for p in projects]
        text_body = "\n\n---\n\n".join(
            render_project(p, include_items) for p in projects
        )
        summary = f"{len(projects)} project{'s' if len(projects) != 1 else ''}"
        return make_result(data=data, summary=summary, text=text_body)

    @mcp.tool(
        name="get-areas",
        annotations=TOOL_ANNOTATIONS["get-areas"],
        tags=tags_for("get-areas"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[list[Area]]),
    )
    async def get_areas(include_items: bool = False, ctx: Context = None) -> ToolResult:
        """[tasks-gtd] Get all areas from Things.

        Args:
            include_items: Include projects and tasks within areas
        """
        if ctx:
            await ctx.info("Fetching areas...")
        areas = db.areas() or []

        if not areas:
            return make_result(data=[], summary="No areas found", text="No areas found")

        data = [to_dict_area(a, include_items) for a in areas]
        text_body = "\n\n---\n\n".join(render_area(a, include_items) for a in areas)
        summary = f"{len(areas)} area{'s' if len(areas) != 1 else ''}"
        return make_result(data=data, summary=summary, text=text_body)

    @mcp.tool(
        name="get-project",
        annotations=TOOL_ANNOTATIONS["get-project"],
        tags=tags_for("get-project"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[Project]),
    )
    async def get_project(name_or_uuid: str, ctx: Context = None) -> ToolResult:
        """[tasks-gtd] Get a single project with full detail by name or UUID.

        Use when: You need full detail on a specific project — its tasks, notes,
        deadline, area, and status. For listing all projects, use get-projects instead.

        Args:
            name_or_uuid: Project name (case-insensitive) or UUID
        """
        if ctx:
            await ctx.info("Looking up project...")

        try:
            project = resolve_item(name_or_uuid, "project")
            uuid = project["uuid"]

            # Resolve area title
            area_id = project.get("area")
            area_title = None
            if area_id:
                try:
                    area = db.get(area_id)
                    if area:
                        area_title = area["title"]
                except Exception:
                    pass

            # Fetch tasks (active + completed) and enrich with checklists.
            active = db.todos(project=uuid, status="incomplete") or []
            completed = db.todos(project=uuid, status="completed") or []

            enriched_tasks: list[dict] = []
            for raw in list(active) + list(completed):
                row = dict(raw)
                try:
                    row["checklist"] = db.checklist_items(row["uuid"]) or []
                except Exception:
                    row["checklist"] = []
                enriched_tasks.append(to_dict_todo(row))

            data = to_dict_project(project, include_items=False)
            data["area_title"] = area_title or data.get("area_title")
            data["tasks"] = enriched_tasks

            # Build the legacy text block (preserved verbatim).
            output = f"**{project.get('title', 'Untitled')}**\n"
            output += f"UUID: {uuid}\n"
            output += f"Status: {project.get('status', 'unknown')}\n"
            if area_id:
                output += f"Area: {area_title}\n" if area_title else ""
            else:
                output += "Area: (none)\n"
            if project.get("deadline"):
                output += f"Deadline: {project['deadline']}\n"
            if project.get("start_date"):
                output += f"Scheduled: {project['start_date']}\n"
            if project.get("creation_date"):
                output += f"Created: {project['creation_date']}\n"
            tags = project.get("tags")
            if tags:
                output += f"Tags: {', '.join(tags)}\n"
            if project.get("notes"):
                output += f"\nNotes:\n{project['notes']}\n"

            if active:
                output += f"\n**Tasks** ({len(active)} active"
                if completed:
                    output += f", {len(completed)} completed"
                output += "):\n"
                for t in active:
                    output += f"  - [ ] {t['title']}"
                    if t.get("deadline"):
                        output += f" (due: {t['deadline']})"
                    output += "\n"
            elif completed:
                output += f"\n**Tasks** (0 active, {len(completed)} completed)\n"
            else:
                output += "\n**No tasks** — GTD: every project needs a next action.\n"

            summary = (
                f"Project '{project.get('title', 'Untitled')}': "
                f"{len(active)} active task{'s' if len(active) != 1 else ''}, "
                f"{len(completed)} completed"
            )
            meta = {
                "active_count": len(active),
                "completed_count": len(completed),
            }
            return make_result(data=data, summary=summary, meta=meta, text=output)

        except ToolError:
            raise
        except Exception:
            logger.error("Error getting project", exc_info=True)
            _error_result("Failed to get project. Check server logs for details.")

    @mcp.tool(
        name="get-area",
        annotations=TOOL_ANNOTATIONS["get-area"],
        tags=tags_for("get-area"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[Area]),
    )
    async def get_area(
        name_or_uuid: str,
        include_items: bool = False,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Get a single area with full detail by name or UUID.

        Use when: Inspecting a specific area before modifying or deleting it,
        or checking what projects and to-dos belong to it. For listing all areas,
        use get-areas instead.

        Args:
            name_or_uuid: Area name (case-insensitive) or UUID
            include_items: Include full project and to-do listings
        """
        if ctx:
            await ctx.info("Looking up area...")

        try:
            area = resolve_item(name_or_uuid, "area")
            uuid = area["uuid"]

            projects = [p for p in (db.projects() or []) if p.get("area") == uuid]
            loose_todos = [
                t for t in (db.todos(area=uuid) or []) if not t.get("project")
            ]

            data = to_dict_area(area, include_items=False)
            if include_items:
                data["projects"] = [to_dict_project(p) for p in projects]
                data["tasks"] = [to_dict_todo(t) for t in loose_todos]
            data["tags"] = list(area.get("tags") or [])

            # Legacy text block.
            output = f"**{area.get('title', 'Untitled')}**\n"
            output += f"UUID: {uuid}\n"
            tags = area.get("tags")
            if tags:
                output += f"Tags: {', '.join(tags)}\n"
            output += f"\nProjects: {len(projects)}\n"
            output += f"Loose to-dos: {len(loose_todos)}\n"

            if include_items:
                if projects:
                    output += "\n**Projects:**\n"
                    for p in projects:
                        status = p.get("status", "")
                        task_count = len(
                            db.todos(project=p["uuid"], status="incomplete") or []
                        )
                        output += f"  - {p['title']} ({status}, {task_count} tasks)\n"
                if loose_todos:
                    output += "\n**Loose To-dos:**\n"
                    for t in loose_todos:
                        output += f"  - {t['title']}\n"

            summary = (
                f"Area '{area.get('title', 'Untitled')}': "
                f"{len(projects)} project{'s' if len(projects) != 1 else ''}, "
                f"{len(loose_todos)} loose to-do{'s' if len(loose_todos) != 1 else ''}"
            )
            meta = {
                "project_count": len(projects),
                "loose_todo_count": len(loose_todos),
            }
            return make_result(data=data, summary=summary, meta=meta, text=output)

        except ToolError:
            raise
        except Exception:
            logger.error("Error getting area", exc_info=True)
            _error_result("Failed to get area. Check server logs for details.")

    @mcp.tool(
        name="get-tags",
        annotations=TOOL_ANNOTATIONS["get-tags"],
        tags=tags_for("get-tags"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[list[Tag]]),
    )
    async def get_tags(include_items: bool = False, ctx: Context = None) -> ToolResult:
        """[tasks-gtd] Get all tags.

        Args:
            include_items: Include items tagged with each tag
        """
        if ctx:
            await ctx.info("Fetching tags...")
        tags = db.tags() or []

        if not tags:
            return make_result(data=[], summary="No tags found", text="No tags found")

        data = [to_dict_tag(t, include_items) for t in tags]
        text_body = "\n\n---\n\n".join(render_tag(t, include_items) for t in tags)
        summary = f"{len(tags)} tag{'s' if len(tags) != 1 else ''}"
        return make_result(data=data, summary=summary, text=text_body)

    @mcp.tool(
        name="show-in-app",
        annotations=TOOL_ANNOTATIONS["show-in-app"],
        tags=tags_for("show-in-app"),
        timeout=10,
        output_schema=output_schema_for(ToolEnvelope[ShowInAppResult]),
    )
    async def show_in_app(
        id: str,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Open a specific item or list in the Things app.

        Args:
            id: Item UUID, or list name: inbox, today, upcoming, anytime, someday, logbook,
                tomorrow, deadlines, repeating, all-projects, logged-projects
        """
        if ctx:
            await ctx.info(f"Opening '{id}' in Things...")

        validate_show_id(id)

        try:
            if not app_state.update_app_state():
                if not launch_things():
                    _error_result("Unable to launch Things app")

            result = show(id=id)
            if not result:
                _error_result(f"Failed to open '{id}'")

            payload = ShowInAppResult(opened=id)
            summary = f"Opened '{id}' in Things"
            return make_result(data=payload.model_dump(), summary=summary, text=summary)

        except ToolError:
            raise
        except Exception:
            logger.error("Error showing in app", exc_info=True)
            _error_result("Failed to show in app. Check server logs for details.")

    @mcp.tool(
        name="get-cache-stats",
        annotations=TOOL_ANNOTATIONS["get-cache-stats"],
        tags=tags_for("get-cache-stats"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[CacheStats]),
    )
    async def get_cache_statistics(ctx: Context = None) -> ToolResult:
        """[tasks-gtd] Get cache performance statistics."""
        if ctx:
            await ctx.info("Fetching cache statistics...")
        stats = get_cache_stats()

        payload = CacheStats(
            entries=stats["entries"],
            hits=stats["hits"],
            misses=stats["misses"],
            hit_rate=str(stats["hit_rate"]),
            total_requests=stats["total_requests"],
        )
        text_body = (
            "Cache Statistics:\n"
            f"- Total entries: {stats['entries']}\n"
            f"- Cache hits: {stats['hits']}\n"
            f"- Cache misses: {stats['misses']}\n"
            f"- Hit rate: {stats['hit_rate']}\n"
            f"- Total requests: {stats['total_requests']}"
        )
        summary = (
            f"Cache: {stats['entries']} entries, "
            f"{stats['hit_rate']} hit rate over {stats['total_requests']} requests"
        )
        return make_result(data=payload.model_dump(), summary=summary, text=text_body)

    @mcp.tool(
        name="triage-insights",
        annotations=TOOL_ANNOTATIONS["triage-insights"],
        tags=tags_for("triage-insights"),
        timeout=5,
        output_schema=output_schema_for(ToolEnvelope[TriageInsights]),
    )
    async def triage_insights_tool(
        days: int = 7,
        category: Optional[str] = None,
        action: Optional[str] = None,
        show_trends: bool = False,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Get insights into your inbox triage patterns.

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
            summary_data = triage_tracker.get_summary(days=days)
            total = summary_data["total"]
            period = f"last {days} days" if days > 0 else "all time"

            if total == 0:
                empty_payload = TriageInsights(
                    period_days=days,
                    total=0,
                    avg_per_day=0.0,
                )
                text_body = (
                    f"No triage activity recorded in the {period}.\n\n"
                    "Triage actions are tracked automatically when you process "
                    "inbox items using complete-task, modify-task, defer-task, etc."
                )
                return make_result(
                    data=empty_payload.model_dump(),
                    summary=f"No triage activity in the {period}.",
                    text=text_body,
                )

            actions = summary_data.get("actions", {}) or {}
            categories = summary_data.get("categories", {}) or {}

            action_stats = [
                TriageActionStats(action=a, count=c, percent=int(c / total * 100))
                for a, c in sorted(actions.items(), key=lambda x: -x[1])
            ]
            category_stats = [
                TriageActionStats(action=cat, count=c, percent=int(c / total * 100))
                for cat, c in sorted(categories.items(), key=lambda x: -x[1])
            ]

            insights: list[str] = []
            cancel_rate = summary_data.get("no_context_cancel_rate", 0.0) or 0.0
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

            payload = TriageInsights(
                period_days=days,
                total=total,
                avg_per_day=float(summary_data.get("avg_per_day", 0.0) or 0.0),
                sessions=summary_data.get("sessions", 0) or 0,
                busiest_day=summary_data.get("busiest_day"),
                actions=action_stats,
                categories=category_stats,
                insights=insights,
                no_context_cancel_rate=float(cancel_rate),
            )

            # Build legacy text body — preserved verbatim from the previous tool.
            avg = summary_data.get("avg_per_day", 0)
            sessions = summary_data.get("sessions", 0)
            text_body = f"# Triage Insights ({period})\n\n"
            text_body += f"**{total} items triaged**"
            if sessions:
                text_body += f" across {sessions} session{'s' if sessions != 1 else ''}"
            text_body += f" | {avg}/day avg"
            busiest = summary_data.get("busiest_day")
            if busiest:
                text_body += f" | Busiest: {busiest}"
            text_body += "\n\n"

            if actions:
                text_body += "## Actions\n\n"
                for stat in action_stats:
                    text_body += f"- {stat.action}: {stat.count} ({stat.percent}%)\n"
                text_body += "\n"
            if categories:
                text_body += "## Categories\n\n"
                for stat in category_stats:
                    text_body += f"- {stat.action}: {stat.count} ({stat.percent}%)\n"
                text_body += "\n"
            if insights:
                text_body += "## Insights\n\n"
                for insight in insights:
                    text_body += f"- {insight}\n"
                text_body += "\n"

            if show_trends:
                trends = triage_tracker.get_trends(weeks=4)
                if trends:
                    text_body += "## Weekly Trends\n\n"
                    for i, week in enumerate(trends):
                        arrow = ""
                        if i < len(trends) - 1:
                            prev = trends[i + 1]["total"]
                            curr = week["total"]
                            if curr > prev:
                                arrow = " ^"
                            elif curr < prev:
                                arrow = " v"
                        text_body += (
                            f"- Week of {week['week_start']}: {week['total']} "
                            f"items{arrow}\n"
                        )
            text_body += f"\nFull dashboard: {get_dashboard_url()}\n"

            summary_line = f"{total} items triaged in the {period} ({avg}/day avg)"
            return make_result(
                data=payload.model_dump(),
                summary=summary_line,
                text=text_body,
                meta={"period_days": days},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in triage insights", exc_info=True)
            _error_result(
                "Failed to analyze triage patterns. Check server logs for details."
            )
