"""Pydantic models for structured tool output.

Every `@mcp.tool` returns a `ToolResult` whose `structured_content` validates
against `ToolEnvelope[<DataT>]`. The envelope is intentionally three fields:

- `data`: the typed payload (a domain model, list of models, write/bulk result, or null)
- `summary`: a one-sentence machine-readable headline (also used as the default
  `TextContent` fallback)
- `meta`: free-form metadata — non-fatal warnings, truncation counts, cache info

Failures are *not* an envelope concern. Tools raise `ToolError`, which FastMCP
maps to MCP's protocol-level `isError: true`. The envelope therefore omits any
`ok` / `success` field.

See: `openspec/changes/structured-json-tool-output/` for the full contract.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class ToolEnvelope(BaseModel, Generic[DataT]):
    """Uniform JSON envelope returned by every tool's `structured_content`."""

    model_config = ConfigDict(extra="forbid")

    data: DataT | None = Field(
        default=None,
        description="Typed payload. Null when the tool's only useful signal is the summary.",
    )
    summary: str = Field(
        ...,
        description="One-sentence machine-readable headline.",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-fatal warnings, truncation counts, cache info.",
    )


# ---------------------------------------------------------------------------
# Domain primitives
# ---------------------------------------------------------------------------


class ChecklistItem(BaseModel):
    """A single checklist item belonging to a Todo."""

    model_config = ConfigDict(extra="forbid")

    title: str
    status: Literal["open", "completed"] = "open"
    uuid: str | None = None


class Todo(BaseModel):
    """A Things 3 to-do item, fully enriched.

    List-view tools (`get-tasks`, `search-tasks`) MAY leave `checklist` empty
    for performance; detail-view tools (`get-project`, `focus-mode`,
    single-item `process-inbox`) MUST populate it via `db.checklist_items()`.
    """

    model_config = ConfigDict(extra="forbid")

    uuid: str
    title: str
    type: Literal["to-do", "project", "heading"] = "to-do"
    status: Literal["incomplete", "completed", "canceled"] = "incomplete"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    start: str | None = None
    start_date: str | None = None
    deadline: str | None = None
    stop_date: str | None = None
    created: str | None = None
    modified: str | None = None
    project: str | None = None
    project_title: str | None = None
    area: str | None = None
    area_title: str | None = None


class Project(BaseModel):
    """A Things 3 project. `tasks` is populated only for detail views."""

    model_config = ConfigDict(extra="forbid")

    uuid: str
    title: str
    type: Literal["project"] = "project"
    status: Literal["incomplete", "completed", "canceled"] = "incomplete"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    start: str | None = None
    start_date: str | None = None
    deadline: str | None = None
    stop_date: str | None = None
    created: str | None = None
    modified: str | None = None
    area: str | None = None
    area_title: str | None = None
    tasks: list[Todo] = Field(default_factory=list)


class Area(BaseModel):
    """A Things 3 area of focus. `projects` and `tasks` populated for detail views."""

    model_config = ConfigDict(extra="forbid")

    uuid: str
    title: str
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    tasks: list[Todo] = Field(default_factory=list)


class Tag(BaseModel):
    """A Things 3 tag."""

    model_config = ConfigDict(extra="forbid")

    uuid: str
    title: str
    shortcut: str | None = None
    parent: str | None = None


# ---------------------------------------------------------------------------
# Write / bulk results
# ---------------------------------------------------------------------------


class WriteResult(BaseModel):
    """Outcome of a write tool that has no rich payload (capture, schedule, defer, ...)."""

    model_config = ConfigDict(extra="forbid")

    acknowledged: bool = Field(
        ...,
        description=(
            "True when the underlying write succeeded. Things' URL scheme returns "
            "no payload, so this reflects whether the URL `open` call returned a "
            "non-error code."
        ),
    )
    thing_id: str | None = Field(
        default=None,
        description="UUID of the created/modified item when the call exposes one.",
    )
    summary: str = Field(..., description="Human-readable confirmation.")


class BulkItemError(BaseModel):
    """A single failure inside a bulk operation."""

    model_config = ConfigDict(extra="forbid")

    task_id: str | None = Field(
        default=None,
        description=(
            "UUID of the item that failed. Null when the failure is per-batch "
            "(e.g. an AppleScript invocation covering N items errored as one)."
        ),
    )
    action: str = Field(
        ...,
        description="The action that was being attempted (`complete`, `cancel`, `defer`, ...).",
    )
    reason: str = Field(..., description="Human-readable failure reason.")


class BulkResult(BaseModel):
    """Outcome of a bulk tool. Carries per-item success/failure detail."""

    model_config = ConfigDict(extra="forbid")

    requested: int = Field(..., description="Total items in the call.")
    succeeded: int = Field(..., description="Items that completed without error.")
    failed: int = Field(..., description="Items that errored.")
    succeeded_ids: list[str] = Field(default_factory=list)
    failed_ids: list[str] = Field(default_factory=list)
    errors: list[BulkItemError] = Field(default_factory=list)
    by_action: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Action -> count, populated for tools that mix actions (e.g. bulk-triage). "
            "Empty for single-action bulk tools."
        ),
    )


# ---------------------------------------------------------------------------
# Specialty payloads
# ---------------------------------------------------------------------------


class FocusResult(BaseModel):
    """Payload for `focus-mode`: the chosen Todo plus why it was chosen."""

    model_config = ConfigDict(extra="forbid")

    task: Todo
    selection_reason: Literal[
        "overdue",
        "today_with_deadline",
        "today",
        "anytime",
    ]
    selection_detail: str | None = Field(
        default=None,
        description="Free-form detail about the selection (e.g. 'deadline was 2026-04-20').",
    )


class ReviewReport(BaseModel):
    """Payload for `daily-review` and `weekly-review`."""

    model_config = ConfigDict(extra="forbid")

    period: Literal["daily", "weekly"]
    today_tasks: list[Todo] = Field(default_factory=list)
    overdue: list[Todo] = Field(default_factory=list)
    completed: list[Todo] = Field(
        default_factory=list,
        description="Completed in the review window.",
    )
    inbox_count: int = 0
    upcoming_count: int = 0
    notes: list[str] = Field(
        default_factory=list,
        description="Free-form review insights (no inbox? overdue count? etc.).",
    )


class TriageActionStats(BaseModel):
    """Per-action count for triage insights."""

    model_config = ConfigDict(extra="forbid")

    action: str
    count: int
    percent: int


class TriageInsights(BaseModel):
    """Payload for `triage-insights`."""

    model_config = ConfigDict(extra="forbid")

    period_days: int
    total: int
    avg_per_day: float
    sessions: int = 0
    busiest_day: str | None = None
    actions: list[TriageActionStats] = Field(default_factory=list)
    categories: list[TriageActionStats] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    no_context_cancel_rate: float = 0.0


class CacheStats(BaseModel):
    """Payload for `get-cache-stats`."""

    model_config = ConfigDict(extra="forbid")

    entries: int
    hits: int
    misses: int
    hit_rate: str
    total_requests: int


class ShowInAppResult(BaseModel):
    """Payload for `show-in-app`."""

    model_config = ConfigDict(extra="forbid")

    opened: str = Field(..., description="The id/list that was opened.")


# ---------------------------------------------------------------------------
# Output schema generation
# ---------------------------------------------------------------------------


def output_schema_for(envelope_cls: type[BaseModel]) -> dict[str, Any]:
    """Return a serialization-mode JSON Schema for an envelope class.

    Used to populate `output_schema=` on `@mcp.tool(...)` decorators. The schema
    is *not* yet ChatGPT-strict-mode-transformed — that happens in the
    `on_list_tools` middleware so non-ChatGPT clients keep the original
    Pydantic schema.

    Usage:

        @mcp.tool(
            name="get-tags",
            output_schema=output_schema_for(ToolEnvelope[list[Tag]]),
        )
        async def get_tags(...) -> ToolResult: ...
    """
    return envelope_cls.model_json_schema(mode="serialization")
