"""GTD Reflect Tools: daily and weekly reviews.

These tools support the "Reflect" stage of GTD - reviewing and updating your system.
"""

from . import reader as db
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from .logging_config import get_logger
from .tool_annotations import TOOL_ANNOTATIONS
from .triage_tracker import triage_tracker
from .settings import get_dashboard_url

logger = get_logger(__name__)


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def register_gtd_reflect_tools(mcp: FastMCP):
    """Register GTD Reflect stage tools with the MCP server."""

    @mcp.tool(
        name="daily-review", annotations=TOOL_ANNOTATIONS["daily-review"], timeout=5
    )
    async def daily_review(ctx: Context = None) -> str:
        """[tasks-gtd] Get a daily overview following GTD daily review.

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
            today_tasks = db.today()
            inbox = db.inbox()

            # Find overdue tasks
            all_todos = db.todos(status="incomplete")
            overdue = [
                t
                for t in all_todos
                if t.get("deadline") and t.get("deadline") < today_str
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
                output += "## Overdue\n\n"
                for t in overdue[:5]:
                    output += (
                        f"- **{t.get('title')}** (deadline: {t.get('deadline')})\n"
                    )
                if len(overdue) > 5:
                    output += f"- ...and {len(overdue) - 5} more\n"
                output += "\n"

            # Overdue projects (convenience feature — GTD doesn't prescribe a daily review)
            overdue_projects = [
                p
                for p in (db.projects() or [])
                if p.get("status") == "incomplete"
                and p.get("deadline")
                and p.get("deadline") < today_str
            ]
            if overdue_projects:
                output += "## Overdue Projects\n\n"
                for p in overdue_projects[:5]:
                    output += (
                        f"- **{p.get('title')}** (deadline: {p.get('deadline')}) "
                        "— use `modify-project` to extend or close\n"
                    )
                if len(overdue_projects) > 5:
                    output += f"- ...and {len(overdue_projects) - 5} more\n"
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
                output += "No tasks scheduled for today. Check anytime tasks or process inbox.\n"
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

        except ToolError:
            raise
        except Exception:
            logger.error("Error in daily review", exc_info=True)
            _error_result("Failed to run daily review. Check server logs for details.")

    @mcp.tool(
        name="weekly-review", annotations=TOOL_ANNOTATIONS["weekly-review"], timeout=10
    )
    async def weekly_review(ctx: Context = None) -> str:
        """[tasks-gtd] Comprehensive GTD weekly review.

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
            inbox = db.inbox()
            if inbox:
                output += f"## Inbox: {len(inbox)} items\n"
                output += "**GTD:** Process to zero before finishing review.\n\n"
            else:
                output += "## Inbox: Clear\n\n"

            # 2. Stalled projects — single query + group-by instead of N queries
            projects = db.projects()
            all_incomplete_todos = db.todos(status="incomplete")

            # Group todos by project UUID
            from collections import defaultdict

            todos_by_project = defaultdict(list)
            for t in all_incomplete_todos or []:
                proj_uuid = t.get("project")
                if proj_uuid:
                    todos_by_project[proj_uuid].append(t)

            stalled = []
            for project in projects or []:
                if project.get("status") != "incomplete":
                    continue
                proj_todos = todos_by_project.get(project.get("uuid"), [])
                # Check if any task is available (anytime or today)
                available = [
                    t
                    for t in proj_todos
                    if t.get("start") in (None, "Anytime", "Today")
                    or t.get("start_date") is None
                    or t.get("start_date") == today_str
                ]
                if not available:
                    stalled.append(project)

            if stalled:
                output += f"## Stalled Projects: {len(stalled)}\n"
                output += "These projects have no available next action:\n\n"
                for p in stalled[:5]:
                    output += (
                        f"- **{p.get('title')}** - Add a next action to make progress\n"
                    )
                if len(stalled) > 5:
                    output += f"- ...and {len(stalled) - 5} more\n"
                output += "\n"
            else:
                output += "## All Projects Have Next Actions\n\n"

            # 2b. Unassigned projects (no area of focus)
            # Note: this is a tool feature — Allen's weekly review does not
            # check project-to-area alignment (that's a higher-horizon exercise)
            unassigned = [
                p
                for p in (projects or [])
                if p.get("status") == "incomplete" and not p.get("area")
            ]
            if unassigned:
                output += f"## Unassigned Projects: {len(unassigned)}\n"
                output += "These projects have no area of focus:\n\n"
                for p in unassigned[:5]:
                    output += (
                        f"- **{p.get('title')}** — assign with "
                        f"`modify-project(area=...)`\n"
                    )
                if len(unassigned) > 5:
                    output += f"- ...and {len(unassigned) - 5} more\n"
                output += "\n"

            # 3. Waiting-for items
            waiting = db.todos(tag="waiting-for", status="incomplete")
            if waiting:
                output += f"## Waiting For: {len(waiting)} items\n\n"
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
            someday = db.someday()
            if someday:
                output += f"## Someday/Maybe: {len(someday)} items\n"
                output += "Consider: Should any of these become active?\n\n"
                for s in (someday or [])[:3]:
                    output += f"- {s.get('title')}\n"
                if len(someday or []) > 3:
                    output += f"- ...and {len(someday) - 3} more\n"
                output += "\n"

            # 5. Completed this week
            completed = db.last("7d", status="completed")
            if completed:
                output += f"## Completed This Week: {len(completed)} items\n"
                output += "Celebrate your accomplishments!\n\n"
                for c in (completed or [])[:5]:
                    output += f"- ~~{c.get('title')}~~\n"
                if len(completed) > 5:
                    output += f"- ...and {len(completed) - 5} more\n"

            # 6. Triage activity this week
            try:
                triage_summary = triage_tracker.get_summary(days=7)
                if triage_summary["total"] > 0:
                    output += "\n## Triage Activity This Week\n\n"
                    total = triage_summary["total"]
                    sessions = triage_summary["sessions"]
                    avg = triage_summary["avg_per_day"]

                    output += f"You triaged {total} item{'s' if total != 1 else ''}"
                    if sessions:
                        output += (
                            f" across {sessions} session{'s' if sessions != 1 else ''}"
                        )
                    output += f" ({avg}/day avg).\n\n"

                    # Action breakdown — plain language
                    actions = triage_summary["actions"]
                    if actions:
                        parts = []
                        for action, count in sorted(
                            actions.items(), key=lambda x: -x[1]
                        ):
                            parts.append(f"{count} {action}")
                        output += "**Actions:** " + ", ".join(parts) + "\n\n"

                    # Top categories
                    categories = triage_summary["categories"]
                    if categories:
                        top = sorted(categories.items(), key=lambda x: -x[1])[:3]
                        parts = [f"{cat} ({count})" for cat, count in top]
                        output += "**Top categories:** " + ", ".join(parts) + "\n\n"

                    # Actionable insight: no-context cancellation rate
                    cancel_rate = triage_summary["no_context_cancel_rate"]
                    if cancel_rate > 0.3:
                        pct = int(cancel_rate * 100)
                        output += (
                            f"**Insight:** {pct}% of canceled items had no context "
                            "at capture. Adding notes when capturing could save "
                            "triage time.\n"
                        )

                    output += f"\nSee full dashboard: {get_dashboard_url()}\n"
            except Exception:
                logger.debug("Triage summary in weekly review failed (non-critical)")

            return output

        except ToolError:
            raise
        except Exception:
            logger.error("Error in weekly review", exc_info=True)
            _error_result("Failed to run weekly review. Check server logs for details.")
