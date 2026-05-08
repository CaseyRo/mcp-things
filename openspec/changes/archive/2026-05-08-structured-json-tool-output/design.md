## Context

Things MCP exposes 32 tools to LLM clients (Claude Desktop, Claude Code, ChatGPT, n8n) over streamable-HTTP. Every tool today returns a `str` assembled by `formatters.py`. There is no `structuredContent` block on responses and no `outputSchema` on `tools/list`, so machine consumers must regex-parse prose to extract UUIDs, dates, tags, checklist items, and parent-link metadata.

FastMCP 3.2.4 (already in `pyproject.toml`) supports structured output two ways:

1. **Annotated return type** (`-> MyModel`): SDK auto-derives both `structuredContent` and `outputSchema`, but the auto-derived `content` text block is **raw JSON** — useless for human-readable surfaces.
2. **`ToolResult(content=[...], structured_content=...)`**: full control over both blocks, but `outputSchema` is **not** auto-derived; it must be passed via `output_schema=` on the decorator.

The mcp-tool-reviewer agent confirmed (a) FastMCP's auto-text is raw JSON, so option 1 regresses Claude Desktop's readable view; (b) the MCP protocol already provides `isError` (set by `ToolError`) and `_meta`, so an envelope-level `ok` field is redundant. Today's `format_todo` already pulls `tags`, `checklist`, `project_title`, `area_title`, and dates when the upstream `things-py` row exposes them — but the *user-facing requirement* is that the **JSON output** carries the same fields, not that we add new fetches. The notable gap is `things-py.get(uuid)` does not include checklist items by default; `db.checklist_items(uuid)` is a separate call. Detail views must enrich.

Constraints:

- Backwards compatibility: every existing client that displays the text block must keep working with no visible diff.
- ChatGPT strict mode (already wired in `ClientCompatibilityMiddleware.on_list_tools` for input schemas) rejects `oneOf`/`anyOf` and demands `additionalProperties: false`. Output schemas need the same treatment.
- Pydantic v2 emits `anyOf: [{type: X}, {type: null}]` for `Optional` fields and uses `$defs` for nested models. The existing `anyOf` flattener may not recurse into `$defs`.
- macOS-only deployment, so we have no async-IO concerns beyond the existing FastMCP threading model.

## Goals / Non-Goals

**Goals:**

- Every tool returns `structuredContent` whose payload validates against a Pydantic model.
- Every tool's `tools/list` entry advertises an `outputSchema`.
- The `content` text block is preserved field-for-field (today's `format_todo` / `format_project` / `format_area` / `format_tag` output, plus the human prose currently appended by individual tools — focus banner, GTD decision tree, etc.).
- Structured payloads carry **full domain detail**: tags, checklist items (for detail views), parent project/area links, deadlines, start/stop dates, status, type — not just title and UUID.
- Bulk tools (`bulk-*`) report per-item success / failure with task IDs and error reasons.
- Output schemas pass through ChatGPT strict-mode transforms in `on_list_tools`.

**Non-Goals:**

- Changing tool *names*, *input schemas*, or any tool's GTD semantics.
- Adding new tools or removing existing ones.
- Replacing the GTD decision-tree prose in `process-inbox` or the focus banner in `focus-mode` — these stay verbatim in the text block; they are not separate JSON fields.
- Re-architecting `formatters.py` further than the `to_dict_*` / `render_*` split — the text helpers keep their current logic.
- Extending the dashboard endpoints (`/dashboard`, `/dashboard/data` are disabled per CLAUDE.md and not in scope).
- Migrating from `things-py` reads to direct SQLite for new fields — the SQLite reader stays as-is and we work with whatever fields the existing readers expose.

## Decisions

### D1. Use `ToolResult` everywhere; do not return annotated models

**Decision**: Every `@mcp.tool` returns `ToolResult(content=[TextContent(type="text", text=render_*(...))], structured_content=envelope.model_dump(mode="json"))`.

**Rationale**: FastMCP's auto-derived text block for annotated model returns is raw JSON (e.g., `'{"title": "Buy milk", "uuid": "ABC-123", ...}'`). That regresses Claude Desktop's readable conversation view, prompt logs, and any human consumer. The proposal's "no breaking change for clients that just display the text" guarantee can only be met by emitting the existing prose explicitly. `ToolResult` is FastMCP's documented escape hatch for this exact case.

**Alternatives considered**:

- *Annotated returns + accept JSON text block*: rejected — visible regression for Claude Desktop users.
- *Annotated returns + custom serialiser hook*: FastMCP 3.2.x exposes no public hook for the auto-text body, and patching the SDK is not justified for a one-time migration.

### D2. Three-field envelope: `data` / `summary` / `meta`

**Decision**:

```python
class ToolEnvelope(BaseModel):
    data: <per-tool model | list | None>  # the structured payload
    summary: str                           # one-sentence machine-readable headline
    meta: dict[str, Any] = Field(default_factory=dict)  # warnings, counts, cache info
```

`summary` is what the LLM quotes back to the user without parsing `data`. For write tools and bulk tools, `summary` is the only useful structured field. `meta` carries non-fatal warnings, total counts when `data` is truncated, and cache-hit indicators.

**Rationale**: MCP already has `isError` (set by `ToolError`) and `_meta` at the protocol level. Re-introducing `ok` and `warnings` at the envelope level duplicates that and forces clients to look in two places. Three fields cover every use case the 32 tools have today.

**Alternatives considered**:

- *Five-field envelope (`ok, data, summary, warnings, meta`)*: rejected per reviewer feedback — `ok` duplicates `isError`, `warnings` belongs in `_meta`/`meta`.
- *No envelope, return raw domain models*: rejected — `summary` is genuinely useful for write/bulk tools, and a uniform shape simplifies client code.

### D3. Per-tool `data` types (typed, not `Any`)

Each tool's `output_schema=` is generated from a tool-specific envelope subclass, so `data` is concretely typed:

| Tool family | `data` type |
|---|---|
| `get-tasks`, `search-tasks`, `process-inbox(all=true)` | `list[Todo]` |
| `get-projects` | `list[Project]` |
| `get-project` | `Project` (with `tasks: list[Todo]` populated) |
| `get-areas` | `list[Area]` |
| `get-area` | `Area` (with `projects` and `tasks` populated) |
| `get-tags` | `list[Tag]` |
| `focus-mode`, `convert-to-project`, `process-inbox` (single) | `Todo` |
| `daily-review`, `weekly-review` | `ReviewReport` |
| `triage-insights` | `TriageInsights` |
| `get-cache-stats` | `CacheStats` |
| `show-in-app` | `ShowInAppResult` |
| `capture-task`, `complete-task`, `schedule-task`, `defer-task`, `delegate-task`, `modify-task`, `plan-project`, `modify-project`, `create-area`, `modify-area`, `delete-area`, `merge-areas` | `WriteResult` |
| `bulk-capture`, `bulk-complete`, `bulk-cancel`, `bulk-modify`, `bulk-triage` | `BulkResult` |

**Rationale**: A typed `data` field gives clients precise output schemas. `WriteResult` and `BulkResult` are reused across many tools; the per-tool envelope is just a thin generic-style alias (`class CaptureTaskEnvelope(ToolEnvelope[WriteResult]): ...`).

### D4. Domain models populated with full detail (the "title only" complaint)

The user explicitly flagged that today the output looks like just title/content. The Pydantic models MUST populate every relevant field whenever the upstream row exposes it:

```python
class ChecklistItem(BaseModel):
    title: str
    status: Literal["open", "completed"]
    uuid: str | None = None

class Todo(BaseModel):
    uuid: str
    title: str
    type: Literal["to-do", "project", "heading"] = "to-do"
    status: Literal["incomplete", "completed", "canceled"] = "incomplete"
    notes: str | None = None
    tags: list[str] = []                         # MUST always be populated (default [])
    checklist: list[ChecklistItem] = []          # detail views: enriched via db.checklist_items(uuid)
    start: str | None = None                     # inbox / anytime / someday / scheduled
    start_date: str | None = None                # ISO date
    deadline: str | None = None                  # ISO date
    stop_date: str | None = None                 # ISO date (completion)
    created: str | None = None                   # ISO date
    modified: str | None = None                  # ISO date when available
    project: str | None = None                   # parent project UUID
    project_title: str | None = None
    area: str | None = None                      # parent area UUID
    area_title: str | None = None

class Project(BaseModel):
    uuid: str
    title: str
    type: Literal["project"] = "project"
    status: Literal["incomplete", "completed", "canceled"] = "incomplete"
    notes: str | None = None
    tags: list[str] = []
    start: str | None = None
    start_date: str | None = None
    deadline: str | None = None
    area: str | None = None
    area_title: str | None = None
    tasks: list[Todo] = []                       # populated for get-project, optional otherwise

class Area(BaseModel):
    uuid: str
    title: str
    notes: str | None = None
    tags: list[str] = []
    projects: list[Project] = []                 # populated for get-area
    tasks: list[Todo] = []                       # populated for get-area (project-less direct todos)

class Tag(BaseModel):
    uuid: str
    title: str
    shortcut: str | None = None
    parent: str | None = None
```

**Enrichment rule**: detail tools (`get-project`, `get-area`, `process-inbox` single-item, `convert-to-project` source readback, `focus-mode`) MUST call `db.checklist_items(uuid)` and populate `checklist` on each Todo. List tools (`get-tasks`, `search-tasks`) MAY omit checklists for performance but MUST populate tags, dates, parent links, status, type.

### D5. `WriteResult` and `BulkResult` shapes

```python
class WriteResult(BaseModel):
    acknowledged: bool                            # URL scheme accepted (Things has no response, so true unless `open` failed)
    thing_id: str | None = None                   # UUID of created/modified item when known
    summary: str                                  # human-readable confirmation

class BulkItemError(BaseModel):
    task_id: str | None = None                    # null when failure is per-batch (e.g. AppleScript error)
    action: str                                   # "complete", "cancel", "defer", ...
    reason: str

class BulkResult(BaseModel):
    requested: int                                # total items in the call
    succeeded: int
    failed: int
    succeeded_ids: list[str] = []
    failed_ids: list[str] = []
    errors: list[BulkItemError] = []              # 1 entry per failure (per-task or per-action-batch)
    by_action: dict[str, int] = {}                # action -> count, populated for bulk-triage
```

**Rationale**: An LLM that calls `bulk-complete` on 5 tasks and gets `{"succeeded": 3, "failed": 2, "succeeded_ids": [...], "failed_ids": [...]}` can immediately retry only the failures or surface them to the user — no follow-up `get-tasks` to diff the state. Reuses the existing `results` dict shape from `tools_batch.py` so the migration is mechanical.

### D6. Schema generation and ChatGPT strict-mode

**Decision**: Each tool decorator passes `output_schema=ToolEnvelope[<DataT>].model_json_schema(mode="serialization")`. The existing `ClientCompatibilityMiddleware.on_list_tools` is extended with `_transform_output_schema` that mirrors the input-schema transforms — `additionalProperties: false`, `anyOf` flattening, nullable-type expansion. The middleware reads `tool.outputSchema` and writes back the transformed dict the same way it currently does for `tool.inputSchema`.

The `anyOf` flattener (currently shallow) is upgraded to recursively walk into `properties`, `items`, `additionalProperties`, and `$defs`. A targeted unit test feeds it the materialised `ToolEnvelope[Todo]` schema and asserts no `anyOf`/`oneOf` survives.

**Rationale**: Pydantic's serialisation-mode JSON Schema for `Optional[str]` is `anyOf: [{type: string}, {type: null}]`, and nested models go in `$defs`. Without recursion, ChatGPT will reject `outputSchema` for any tool returning a model with optional fields — i.e. all of them.

### D7. Migration: one tool family at a time

**Decision**: Phased migration in this order:

1. Models module + envelope + per-tool envelope subclasses (no behaviour change).
2. `formatters.py` split into `to_dict_*` + `render_*` (no caller change yet — `format_*` becomes `render_*` shim that calls `to_dict_*` then renders).
3. Migrate utility tools (`get-cache-stats`, `show-in-app`, `get-tags`) — smallest surface, easiest to verify.
4. Migrate read tools (`get-tasks`, `get-projects`, `get-project`, `get-areas`, `get-area`, `search-tasks`, `focus-mode`, `process-inbox`).
5. Migrate write tools (capture, schedule, defer, delegate, complete, modify-*, create-area, plan-project, merge-areas, delete-area, convert-to-project).
6. Migrate batch tools (bulk-*) with the new `BulkResult` shape.
7. Extend `on_list_tools` to transform output schemas; add the `$defs`-aware `anyOf` flattener.
8. Migrate review/insight tools (`daily-review`, `weekly-review`, `triage-insights`).

Each step lands as a separate commit; tests gate each commit. Tools not yet migrated continue returning `str` and FastMCP wraps them transparently — there is no flag day.

## Risks / Trade-offs

- **Risk**: Auto-derived text block being raw JSON regresses Claude Desktop's readable view → **Mitigation**: D1 mandates explicit `TextContent`; CI test asserts every tool's text block contains its rendered prose markers (e.g. `Title:`, `**FOCUS:`).
- **Risk**: `output_schema=` on every decorator is verbose → **Mitigation**: helper `output_schema_for(data_model)` returns the materialised, strict-mode-safe schema; decorators read `output_schema=output_schema_for(Todo)` (one-liner).
- **Risk**: Pydantic `$defs` references break ChatGPT strict mode → **Mitigation**: D6 upgrades the flattener; unit test guards against regressions.
- **Risk**: Detail-view enrichment (`db.checklist_items(uuid)` per Todo) adds N+1 queries on `get-project` for projects with many tasks → **Mitigation**: only fetch checklists for the project's `tasks` list when the tool is `get-project` (single project view); document that `get-tasks` does not include checklists; keep `things-py` SQLite cache warm.
- **Risk**: `ToolResult.model_dump(mode="json")` calls add ~µs per tool call → **Mitigation**: negligible compared to the AppleScript / URL-scheme latency Things imposes; no optimisation needed.
- **Risk**: Existing tests assert on exact text bodies → **Mitigation**: keep `render_*` output byte-identical to today's `format_*`; run the full test suite before each migration commit; the `addopts` "not real" default keeps CI clean.
- **Risk**: n8n's null-stripping middleware (`on_call_tool`) operates on input only — output `null`s pass through. ChatGPT's strict mode requires `null`-typed nullable fields, while n8n is fine with them → **Mitigation**: emit `null` for all optional fields uniformly (Pydantic default) and rely on input-side null-strip + output-side strict transforms; no new middleware needed.

## Migration Plan

1. **Land model module** behind no flag. Tests for model serialisation and JSON-Schema strict-mode validity.
2. **Land formatter split** behind no flag (helpers exist; old `format_*` names redirect).
3. **Per-family migration commits** (utility → read → write → batch → review). Each commit:
   - Switches the family's tools to `ToolResult` + envelope.
   - Adds/updates unit tests asserting `structuredContent` shape, `TextContent` parity, and `outputSchema` advertisement.
4. **Middleware extension commit** (after at least one tool migrated): adds output-schema strict-mode transform and `$defs`-aware flattener.
5. **Documentation commit**: update `CLAUDE.md` (Key Patterns + Client Compatibility sections) with envelope shape and the "tools/list publishes outputSchema" note.

**Rollback**: any individual tool can revert to `return str` independently — FastMCP keeps wrapping `str` returns into `TextContent`, so a partial revert is safe and visible only to consumers reading `structuredContent`.

## Open Questions

- Should `summary` be human prose ("Captured 3 items: Buy milk, Call Alex, Email Sam") or terse machine prose ("3 items captured")? **Working answer**: terse machine prose, since the `TextContent` block carries the human prose. Confirm during implementation review.
- For `focus-mode`, should the `selection_reason` ("OVERDUE", "Due TODAY") live in `meta` or in a dedicated `data.reason` field? **Working answer**: dedicated field on a `FocusResult` envelope so clients can branch on it without parsing.
- For `process-inbox` (default mode), should the GTD decision-tree prose live in `data` (so machine clients see the same guidance) or only in `TextContent`? **Working answer**: `TextContent` only — machines should call the next tool, not read the tree. Revisit if a client requests it.
