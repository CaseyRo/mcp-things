"""Batch Tools: bulk operations that collapse N round-trips into 1 MCP call.

The `bulk-*` prefix denotes the N-item version of a singular tool:
- bulk-capture = N x capture-task (uses Things JSON URL scheme, 1 URL open)
- bulk-complete = N x complete-task (single AppleScript with UUID loop)
- bulk-cancel = N x modify-task(canceled=True) (single AppleScript with UUID loop)
- bulk-modify = N x modify-task (single AppleScript, uniform changes)
- bulk-triage = N x (complete|cancel|defer|schedule|delegate|assign) grouped by action
"""

from typing import Optional, List, Literal

import things
from pydantic import BaseModel, Field, model_validator
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult

from .models import BulkItemError, BulkResult, ToolEnvelope, output_schema_for
from .tool_results import bulk_result
from .url_scheme import (
    build_todo_object,
    execute_json,
    update_todo,
    execute_url,
    launch_things,
)
from .applescript_bridge import run_applescript
from .logging_config import get_logger
from .cache import invalidate_caches_for
from .tag_handler import ensure_tags_exist
from .triage_tracker import triage_tracker
from .utils import app_state
from .input_validation import validate_uuid_list, validate_tag_names
from .tool_annotations import TOOL_ANNOTATIONS, tags_for
from .resolvers import resolve_list_id

logger = get_logger(__name__)


# --- Pydantic Models for typed LLM schemas ---


class CaptureItem(BaseModel):
    """A single item for bulk capture."""

    title: str = Field(..., description="What needs to be done")
    notes: Optional[str] = Field(None, description="Additional details")
    when: Optional[Literal["today", "tomorrow", "evening", "anytime", "someday"]] = (
        Field(
            None, description="Schedule override (takes precedence over default_when)"
        )
    )
    tags: Optional[List[str]] = Field(
        None, description="Context tags like @computer, @phone"
    )
    deadline: Optional[str] = Field(None, description="Deadline in YYYY-MM-DD format")


class TriageDecision(BaseModel):
    """A single triage decision for an inbox item.

    Required fields per action:
    - complete/cancel: no additional fields
    - defer/schedule: `when` is required
    - delegate: `delegated_to` is required
    - assign: `project` is required (routes to convert-to-project)
    """

    task_id: str = Field(..., description="UUID of the task")
    action: Literal["complete", "cancel", "defer", "schedule", "delegate", "assign"] = (
        Field(..., description="What to do with this task")
    )
    when: Optional[str] = Field(
        None,
        description="Required for defer/schedule (e.g. 'tomorrow', 'next-week', 'someday', YYYY-MM-DD)",
    )
    delegated_to: Optional[str] = Field(
        None, description="Required for delegate — who to hand this to"
    )
    project: Optional[str] = Field(
        None, description="Required for assign — project name or UUID"
    )
    notes: Optional[str] = Field(None, description="Optional notes to append")

    @model_validator(mode="after")
    def check_required_fields(self):
        if self.action in ("defer", "schedule") and not self.when:
            raise ValueError(f"'when' is required for action='{self.action}'")
        if self.action == "delegate" and not self.delegated_to:
            raise ValueError("'delegated_to' is required for action='delegate'")
        if self.action == "assign" and not self.project:
            raise ValueError("'project' is required for action='assign'")
        return self


def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)


def _ensure_things_running():
    """Ensure Things app is running, raise ToolError if not."""
    if not app_state.update_app_state():
        if not launch_things():
            _error_result("Unable to launch Things app")


def _prefetch_titles(task_ids: List[str]) -> dict:
    """Pre-fetch task titles for result messages. Returns {uuid: title}."""
    titles = {}
    for tid in task_ids:
        try:
            task = things.get(tid)
            if task:
                titles[tid] = task.get("title", tid)
            else:
                titles[tid] = tid
        except Exception:
            titles[tid] = tid
    return titles


def register_batch_tools(mcp: FastMCP):
    """Register batch tools with the MCP server."""

    @mcp.tool(
        name="bulk-capture",
        annotations=TOOL_ANNOTATIONS["bulk-capture"],
        tags=tags_for("bulk-capture"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[BulkResult]),
    )
    async def bulk_capture(
        items: List[CaptureItem] = Field(..., min_length=1, max_length=50),
        default_when: Optional[
            Literal["today", "tomorrow", "evening", "anytime", "someday"]
        ] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Create multiple inbox items in one call. Batch version of capture-task.

        GTD Stage: Capture
        Use when: Capturing multiple items at once (meeting notes, braindump, etc.)

        Args:
            items: List of items to capture (1-50). Each has title (required), notes, when, tags, deadline.
            default_when: Default schedule for items without an explicit 'when' value.
        """
        if ctx:
            await ctx.info(f"Bulk capturing {len(items)} items...")
            await ctx.report_progress(
                progress=0, total=len(items), message="Preparing capture"
            )

        if not items:
            _error_result("items cannot be empty")
        if len(items) > 50:
            _error_result(
                f"Too many items ({len(items)}). Maximum is 50. Split into multiple calls."
            )

        try:
            _ensure_things_running()

            # Collect all tags and ensure they exist
            all_tags = set()
            for item in items:
                if item.tags:
                    validate_tag_names(item.tags)
                    all_tags.update(item.tags)
            if all_tags:
                ensure_tags_exist(list(all_tags))

            # Build todo objects for JSON API
            todo_objects = []
            for item in items:
                effective_when = item.when or default_when
                todo_obj = build_todo_object(
                    title=item.title,
                    notes=item.notes,
                    when=effective_when,
                    deadline=item.deadline,
                    tags=item.tags,
                )
                todo_objects.append(todo_obj)

            # Single JSON URL scheme call for all items
            success = execute_json(todo_objects)
            if not success:
                _error_result("Failed to create items via Things JSON API")

            if ctx:
                await ctx.report_progress(
                    progress=len(items), total=len(items), message="Capture complete"
                )

            invalidate_caches_for(["get-inbox", "get-tasks"])

            titles = [item.title for item in items]
            text_body = f"Captured {len(items)} items"
            if default_when:
                text_body += f" (default schedule: {default_when})"
            text_body += ":\n"
            for title in titles:
                text_body += f"- {title}\n"

            # Things JSON URL scheme returns no UUIDs; report titles as proxy IDs
            # so consumers can still correlate per-item success.
            return bulk_result(
                requested=len(items),
                succeeded_ids=titles,
                failed_ids=[],
                errors=[],
                summary=f"Captured {len(items)} items.",
                text=text_body,
                meta={"default_when": default_when},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in bulk-capture", exc_info=True)
            _error_result("Failed to bulk capture. Check server logs for details.")

    @mcp.tool(
        name="bulk-complete",
        annotations=TOOL_ANNOTATIONS["bulk-complete"],
        tags=tags_for("bulk-complete"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[BulkResult]),
    )
    async def bulk_complete(
        task_ids: List[str] = Field(..., min_length=1, max_length=50),
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Mark multiple tasks complete in one call. Batch version of complete-task.

        GTD Stage: Engage
        Use when: Completing several tasks at once (end-of-day cleanup, batch processing).

        Args:
            task_ids: List of task UUIDs to complete (1-50).
        """
        if ctx:
            await ctx.info(f"Completing {len(task_ids)} tasks...")
            await ctx.report_progress(
                progress=0, total=len(task_ids), message="Completing tasks"
            )

        validate_uuid_list(task_ids)

        try:
            _ensure_things_running()
            titles = _prefetch_titles(task_ids)

            # Single AppleScript with UUID loop
            uuid_list = ", ".join(f'"{tid}"' for tid in task_ids)
            script = (
                f'tell application "Things3"\n'
                f"  repeat with tid in {{{uuid_list}}}\n"
                f"    set status of (to do id tid) to completed\n"
                f"  end repeat\n"
                f"end tell"
            )
            result = run_applescript(script)
            if result is False:
                _error_result(
                    f"AppleScript failed. {len(task_ids)} tasks may be partially completed. "
                    "Verify with get-tasks and retry remaining."
                )

            if ctx:
                await ctx.report_progress(
                    progress=len(task_ids),
                    total=len(task_ids),
                    message="Tasks completed",
                )

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime"]
            )

            # Track triage actions
            for tid in task_ids:
                try:
                    triage_tracker.record(
                        task_id=tid,
                        task_title=titles.get(tid, ""),
                        action="completed",
                        action_details={"bulk": True},
                    )
                except Exception:
                    pass

            completed_titles = [titles.get(tid, tid) for tid in task_ids]
            text_body = f"Completed {len(task_ids)} tasks:\n" + "\n".join(
                f"- {t}" for t in completed_titles
            )
            return bulk_result(
                requested=len(task_ids),
                succeeded_ids=task_ids,
                failed_ids=[],
                errors=[],
                summary=f"Completed {len(task_ids)} tasks.",
                text=text_body,
                by_action={"complete": len(task_ids)},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in bulk-complete", exc_info=True)
            _error_result("Failed to bulk complete. Check server logs for details.")

    @mcp.tool(
        name="bulk-cancel",
        annotations=TOOL_ANNOTATIONS["bulk-cancel"],
        tags=tags_for("bulk-cancel"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[BulkResult]),
    )
    async def bulk_cancel(
        task_ids: List[str] = Field(..., min_length=1, max_length=50),
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Cancel multiple tasks in one call. Batch version of modify-task(canceled=True).

        GTD Stage: Engage
        Use when: Canceling several tasks at once (cleanup, scope change).

        Args:
            task_ids: List of task UUIDs to cancel (1-50).
        """
        if ctx:
            await ctx.info(f"Canceling {len(task_ids)} tasks...")
            await ctx.report_progress(
                progress=0, total=len(task_ids), message="Canceling tasks"
            )

        validate_uuid_list(task_ids)

        try:
            _ensure_things_running()
            titles = _prefetch_titles(task_ids)

            uuid_list = ", ".join(f'"{tid}"' for tid in task_ids)
            script = (
                f'tell application "Things3"\n'
                f"  repeat with tid in {{{uuid_list}}}\n"
                f"    set status of (to do id tid) to canceled\n"
                f"  end repeat\n"
                f"end tell"
            )
            result = run_applescript(script)
            if result is False:
                _error_result(
                    f"AppleScript failed. {len(task_ids)} tasks may be partially canceled. "
                    "Verify with get-tasks and retry remaining."
                )

            if ctx:
                await ctx.report_progress(
                    progress=len(task_ids),
                    total=len(task_ids),
                    message="Tasks canceled",
                )

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime"]
            )

            for tid in task_ids:
                try:
                    triage_tracker.record(
                        task_id=tid,
                        task_title=titles.get(tid, ""),
                        action="canceled",
                        action_details={"bulk": True},
                    )
                except Exception:
                    pass

            canceled_titles = [titles.get(tid, tid) for tid in task_ids]
            text_body = f"Canceled {len(task_ids)} tasks:\n" + "\n".join(
                f"- {t}" for t in canceled_titles
            )
            return bulk_result(
                requested=len(task_ids),
                succeeded_ids=task_ids,
                failed_ids=[],
                errors=[],
                summary=f"Canceled {len(task_ids)} tasks.",
                text=text_body,
                by_action={"cancel": len(task_ids)},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in bulk-cancel", exc_info=True)
            _error_result("Failed to bulk cancel. Check server logs for details.")

    @mcp.tool(
        name="bulk-modify",
        annotations=TOOL_ANNOTATIONS["bulk-modify"],
        tags=tags_for("bulk-modify"),
        timeout=30,
        output_schema=output_schema_for(ToolEnvelope[BulkResult]),
    )
    async def bulk_modify(
        task_ids: List[str] = Field(..., min_length=1, max_length=50),
        when: Optional[str] = None,
        add_tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        area: Optional[str] = None,
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Apply the same modification to multiple tasks. Batch version of modify-task.

        GTD Stage: Organize
        Use when: Moving, tagging, or rescheduling many tasks at once.
        Provide project OR area, not both.

        Args:
            task_ids: List of task UUIDs to modify (1-50).
            when: Reschedule all tasks (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD).
            add_tags: Tags to add to all tasks (e.g. ["@computer"]).
            project: Move all tasks to this project (name or UUID). Mutually exclusive with area.
            area: Move all tasks to this area (name or UUID). Mutually exclusive with project.
        """
        if ctx:
            await ctx.info(f"Modifying {len(task_ids)} tasks...")

        validate_uuid_list(task_ids)

        if project and area:
            _error_result(
                "Provide project OR area, not both — they are mutually exclusive."
            )

        if not any([when, add_tags, project, area]):
            _error_result(
                "Provide at least one modification (when, add_tags, project, or area)."
            )

        try:
            _ensure_things_running()

            if add_tags:
                validate_tag_names(add_tags)
                ensure_tags_exist(add_tags)

            # Resolve project/area to UUID if provided by name
            list_id = None
            if project:
                list_id = resolve_list_id(project, "project")
            elif area:
                list_id = resolve_list_id(area, "area")

            # Use URL scheme update for each task (update doesn't support batching)
            succeeded_ids: list[str] = []
            failed_ids: list[str] = []
            errors: list[BulkItemError] = []
            total = len(task_ids)
            for idx, tid in enumerate(task_ids, start=1):
                if ctx:
                    await ctx.report_progress(
                        progress=idx,
                        total=total,
                        message=f"Modifying task {idx}/{total}",
                    )
                url = update_todo(
                    id=tid,
                    when=when,
                    add_tags=add_tags,
                    list_id=list_id,
                )
                success = execute_url(url)
                if success:
                    succeeded_ids.append(tid)
                else:
                    failed_ids.append(tid)
                    errors.append(
                        BulkItemError(
                            task_id=tid,
                            action="modify",
                            reason="URL scheme failed",
                        )
                    )
                    logger.warning(f"Failed to modify task {tid}")

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime"]
            )

            changes = []
            if when:
                changes.append(f"scheduled to {when}")
            if add_tags:
                changes.append(f"tagged with {', '.join(add_tags)}")
            if project:
                changes.append(f"moved to project {project}")
            if area:
                changes.append(f"moved to area {area}")

            text_body = (
                f"Modified {len(succeeded_ids)}/{len(task_ids)} tasks: "
                f"{', '.join(changes)}."
            )
            return bulk_result(
                requested=len(task_ids),
                succeeded_ids=succeeded_ids,
                failed_ids=failed_ids,
                errors=errors,
                summary=f"Modified {len(succeeded_ids)}/{len(task_ids)} tasks.",
                text=text_body,
                by_action={"modify": len(succeeded_ids)},
                meta={"changes": changes},
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in bulk-modify", exc_info=True)
            _error_result("Failed to bulk modify. Check server logs for details.")

    @mcp.tool(
        name="bulk-triage",
        annotations=TOOL_ANNOTATIONS["bulk-triage"],
        tags=tags_for("bulk-triage"),
        timeout=60,
        output_schema=output_schema_for(ToolEnvelope[BulkResult]),
    )
    async def bulk_triage(
        decisions: List[TriageDecision] = Field(..., min_length=1, max_length=100),
        ctx: Context = None,
    ) -> ToolResult:
        """[tasks-gtd] Process multiple inbox decisions in one call. Use after process-inbox(all=True).

        GTD Stage: Clarify + Organize
        Use when: You have reviewed all inbox items and want to submit all decisions at once.
        Replaces the one-at-a-time loop of process-inbox + action tool per item.

        Performance: complete/cancel actions are O(1) via single AppleScript.
        defer/schedule/delegate are O(N) URL opens but still only 1 MCP round-trip.

        Args:
            decisions: List of triage decisions (1-100). Each has task_id, action, and action-specific fields.
        """
        if ctx:
            await ctx.info(f"Triaging {len(decisions)} items...")

        if not decisions:
            _error_result("decisions cannot be empty")

        try:
            _ensure_things_running()

            # Validate all task_ids
            all_ids = [d.task_id for d in decisions]
            validate_uuid_list(all_ids, max_length=100)

            # Group by action type
            completes = [d for d in decisions if d.action == "complete"]
            cancels = [d for d in decisions if d.action == "cancel"]
            defers = [d for d in decisions if d.action == "defer"]
            schedules = [d for d in decisions if d.action == "schedule"]
            delegates = [d for d in decisions if d.action == "delegate"]
            assigns = [d for d in decisions if d.action == "assign"]

            results = {"processed": 0, "failed": 0, "failures": []}
            succeeded_ids: list[str] = []
            failed_ids: list[str] = []
            errors: list[BulkItemError] = []
            titles = _prefetch_titles(all_ids)

            # Progress tracking: batched complete/cancel count as one step each;
            # the per-item URL-scheme actions report incremental progress.
            total_steps = len(decisions)
            done_steps = 0

            async def _tick(amount: int = 1, message: str = "") -> None:
                nonlocal done_steps
                done_steps += amount
                if ctx:
                    await ctx.report_progress(
                        progress=min(done_steps, total_steps),
                        total=total_steps,
                        message=message or f"Triaged {done_steps}/{total_steps}",
                    )

            # Batch complete (single AppleScript)
            if completes:
                ids = [d.task_id for d in completes]
                uuid_list = ", ".join(f'"{tid}"' for tid in ids)
                script = (
                    f'tell application "Things3"\n'
                    f"  repeat with tid in {{{uuid_list}}}\n"
                    f"    set status of (to do id tid) to completed\n"
                    f"  end repeat\n"
                    f"end tell"
                )
                if run_applescript(script) is not False:
                    results["processed"] += len(completes)
                    for d in completes:
                        succeeded_ids.append(d.task_id)
                        try:
                            triage_tracker.record(
                                task_id=d.task_id,
                                task_title=titles.get(d.task_id, ""),
                                action="completed",
                                action_details={"bulk_triage": True},
                            )
                        except Exception:
                            pass
                    await _tick(len(completes), "Completed inbox items")
                else:
                    results["failed"] += len(completes)
                    results["failures"].append(
                        {
                            "action": "complete",
                            "count": len(completes),
                            "reason": "AppleScript failed",
                        }
                    )
                    for d in completes:
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action="complete",
                                reason="AppleScript failed",
                            )
                        )
                    await _tick(len(completes), "Complete batch failed")

            # Batch cancel (single AppleScript)
            if cancels:
                ids = [d.task_id for d in cancels]
                uuid_list = ", ".join(f'"{tid}"' for tid in ids)
                script = (
                    f'tell application "Things3"\n'
                    f"  repeat with tid in {{{uuid_list}}}\n"
                    f"    set status of (to do id tid) to canceled\n"
                    f"  end repeat\n"
                    f"end tell"
                )
                if run_applescript(script) is not False:
                    results["processed"] += len(cancels)
                    for d in cancels:
                        succeeded_ids.append(d.task_id)
                        try:
                            triage_tracker.record(
                                task_id=d.task_id,
                                task_title=titles.get(d.task_id, ""),
                                action="canceled",
                                action_details={"bulk_triage": True},
                            )
                        except Exception:
                            pass
                    await _tick(len(cancels), "Canceled inbox items")
                else:
                    results["failed"] += len(cancels)
                    results["failures"].append(
                        {
                            "action": "cancel",
                            "count": len(cancels),
                            "reason": "AppleScript failed",
                        }
                    )
                    for d in cancels:
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action="cancel",
                                reason="AppleScript failed",
                            )
                        )
                    await _tick(len(cancels), "Cancel batch failed")

            # Defer/schedule (individual URL scheme calls)
            for d in defers + schedules:
                await _tick(message=f"{d.action.capitalize()} item")
                try:
                    # Append notes if provided
                    if d.notes:
                        url = update_todo(id=d.task_id, append_notes=f"\n{d.notes}")
                        execute_url(url)

                    when_value = d.when
                    if d.action == "defer" and when_value == "someday":
                        when_value = "someday"
                    url = update_todo(id=d.task_id, when=when_value)
                    if execute_url(url):
                        results["processed"] += 1
                        succeeded_ids.append(d.task_id)
                        triage_tracker.record(
                            task_id=d.task_id,
                            task_title=titles.get(d.task_id, ""),
                            action=f"{d.action}d",
                            action_details={"when": d.when, "bulk_triage": True},
                        )
                    else:
                        results["failed"] += 1
                        results["failures"].append(
                            {
                                "task_id": d.task_id,
                                "action": d.action,
                                "reason": "URL scheme failed",
                            }
                        )
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action=d.action,
                                reason="URL scheme failed",
                            )
                        )
                except Exception as e:
                    results["failed"] += 1
                    results["failures"].append(
                        {"task_id": d.task_id, "action": d.action, "reason": str(e)}
                    )
                    failed_ids.append(d.task_id)
                    errors.append(
                        BulkItemError(
                            task_id=d.task_id,
                            action=d.action,
                            reason=str(e),
                        )
                    )

            # Delegate (individual URL scheme calls — adds waiting-for tag + notes)
            for d in delegates:
                await _tick(message="Delegating item")
                try:
                    ensure_tags_exist(["waiting-for"])
                    delegate_notes = f"Delegated to: {d.delegated_to}"
                    if d.notes:
                        delegate_notes += f"\n{d.notes}"
                    url = update_todo(
                        id=d.task_id,
                        append_notes=f"\n{delegate_notes}",
                        add_tags=["waiting-for"],
                    )
                    if execute_url(url):
                        results["processed"] += 1
                        succeeded_ids.append(d.task_id)
                        triage_tracker.record(
                            task_id=d.task_id,
                            task_title=titles.get(d.task_id, ""),
                            action="delegated",
                            action_details={
                                "delegated_to": d.delegated_to,
                                "bulk_triage": True,
                            },
                        )
                    else:
                        results["failed"] += 1
                        results["failures"].append(
                            {
                                "task_id": d.task_id,
                                "action": "delegate",
                                "reason": "URL scheme failed",
                            }
                        )
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action="delegate",
                                reason="URL scheme failed",
                            )
                        )
                except Exception as e:
                    results["failed"] += 1
                    results["failures"].append(
                        {"task_id": d.task_id, "action": "delegate", "reason": str(e)}
                    )
                    failed_ids.append(d.task_id)
                    errors.append(
                        BulkItemError(
                            task_id=d.task_id,
                            action="delegate",
                            reason=str(e),
                        )
                    )

            # Assign to project (individual convert-to-project calls)
            for d in assigns:
                await _tick(message="Assigning item to a project")
                try:
                    from .url_scheme import add_project_with_tasks

                    task = things.get(d.task_id)
                    if not task:
                        results["failed"] += 1
                        results["failures"].append(
                            {
                                "task_id": d.task_id,
                                "action": "assign",
                                "reason": "Task not found",
                            }
                        )
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action="assign",
                                reason="Task not found",
                            )
                        )
                        continue

                    # Create project from task
                    url = add_project_with_tasks(
                        title=task.get("title", "New Project"),
                        tasks=[],
                        notes=task.get("notes"),
                        tags=task.get("tags"),
                        area=task.get("area_title"),
                    )
                    if execute_url(url):
                        # Cancel original task
                        cancel_url = update_todo(id=d.task_id, canceled=True)
                        execute_url(cancel_url)
                        results["processed"] += 1
                        succeeded_ids.append(d.task_id)
                        triage_tracker.record(
                            task_id=d.task_id,
                            task_title=titles.get(d.task_id, ""),
                            action="converted-to-project",
                            action_details={"bulk_triage": True},
                        )
                    else:
                        results["failed"] += 1
                        results["failures"].append(
                            {
                                "task_id": d.task_id,
                                "action": "assign",
                                "reason": "Failed to create project",
                            }
                        )
                        failed_ids.append(d.task_id)
                        errors.append(
                            BulkItemError(
                                task_id=d.task_id,
                                action="assign",
                                reason="Failed to create project",
                            )
                        )
                except Exception as e:
                    results["failed"] += 1
                    results["failures"].append(
                        {"task_id": d.task_id, "action": "assign", "reason": str(e)}
                    )
                    failed_ids.append(d.task_id)
                    errors.append(
                        BulkItemError(
                            task_id=d.task_id,
                            action="assign",
                            reason=str(e),
                        )
                    )

            invalidate_caches_for(
                ["get-tasks", "get-today", "get-inbox", "get-anytime", "get-projects"]
            )

            # Build summary
            action_counts: dict[str, int] = {}
            for d in decisions:
                action_counts[d.action] = action_counts.get(d.action, 0) + 1

            output = f"Triaged {results['processed']}/{len(decisions)} items"
            if results["failed"] > 0:
                output += f" ({results['failed']} failed)"
            output += ":\n"
            for action, count in action_counts.items():
                output += f"- {action}: {count}\n"

            if results["failures"]:
                output += "\nFailures:\n"
                for f in results["failures"]:
                    if "task_id" in f:
                        output += (
                            f"- {f['action']} "
                            f"{titles.get(f['task_id'], f['task_id'])}: "
                            f"{f['reason']}\n"
                        )
                    else:
                        output += (
                            f"- {f['action']} ({f['count']} items): {f['reason']}\n"
                        )

            return bulk_result(
                requested=len(decisions),
                succeeded_ids=succeeded_ids,
                failed_ids=failed_ids,
                errors=errors,
                summary=(
                    f"Triaged {results['processed']}/{len(decisions)} items"
                    + (f" ({results['failed']} failed)" if results["failed"] else "")
                    + "."
                ),
                text=output,
                by_action=action_counts,
            )

        except ToolError:
            raise
        except Exception:
            logger.error("Error in bulk-triage", exc_info=True)
            _error_result("Failed to bulk triage. Check server logs for details.")
