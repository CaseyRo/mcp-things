## ADDED Requirements

### Requirement: Tools SHALL return a typed JSON envelope on every successful call

Every `@mcp.tool` registered on the server MUST return a `ToolResult` whose `structured_content` is a JSON object validating against a `ToolEnvelope` Pydantic model with exactly three top-level fields: `data`, `summary`, and `meta`. The `data` field's type SHALL be tool-specific (a domain model, a list of domain models, a `WriteResult`, a `BulkResult`, or `null` for tools whose only signal is `summary`). The `summary` field SHALL be a single-sentence machine-readable headline. The `meta` field SHALL be an object holding non-fatal warnings, truncation counts, cache hit indicators, and similar metadata; it MAY be empty.

The envelope SHALL NOT include an `ok`, `success`, or `isError` field. Tool failures MUST be raised as `ToolError`, which FastMCP maps to MCP's protocol-level `isError: true`.

#### Scenario: Read tool returns Todo list envelope

- **WHEN** a client calls `get-tasks(view="today")` and the call succeeds
- **THEN** the response's `structured_content` is `{"data": [<Todo>, ...], "summary": "<headline>", "meta": {...}}`
- **AND** every entry in `data` validates against the `Todo` model
- **AND** the response has no envelope-level `ok` field
- **AND** the MCP `isError` flag is `false`

#### Scenario: Write tool returns WriteResult envelope

- **WHEN** a client calls `capture-task(title="Buy milk")` and the URL scheme succeeds
- **THEN** `structured_content.data` validates against `WriteResult` with `acknowledged: true` and `summary` reflecting the captured title
- **AND** `structured_content.summary` is a one-sentence headline (e.g. `"Captured to Inbox: Buy milk"`)

#### Scenario: Tool failure surfaces as MCP isError

- **WHEN** a tool encounters an error condition (invalid input, Things app unavailable, etc.)
- **THEN** the tool raises `ToolError("<message>")`
- **AND** the response has MCP `isError: true`
- **AND** no `structured_content` envelope is emitted

### Requirement: Domain model payloads SHALL include the full set of Things fields

The structured payload for any Todo, Project, Area, or Tag SHALL populate every field that the upstream `things-py` / SQLite reader exposes for that row. At minimum, a Todo MUST carry `uuid`, `title`, `type`, `status`, `notes`, `tags`, `start`, `start_date`, `deadline`, `stop_date`, `created`, `project`, `project_title`, `area`, `area_title`. A Project MUST carry `uuid`, `title`, `type`, `status`, `notes`, `tags`, `start`, `start_date`, `deadline`, `area`, `area_title`. An Area MUST carry `uuid`, `title`, `notes`, `tags`. A Tag MUST carry `uuid`, `title`, `shortcut`.

Detail-view tools (`get-project`, `get-area`, `focus-mode`, single-item `process-inbox`, `convert-to-project` source readback) SHALL enrich each Todo with its checklist by calling `db.checklist_items(uuid)` and populating `Todo.checklist` as a list of `ChecklistItem` (each with `title`, `status`, `uuid`). List-view tools (`get-tasks`, `search-tasks`, `process-inbox(all=true)`) MAY omit checklists for performance but MUST still populate tags, dates, parent links, status, and type.

Optional fields that are not present in the upstream row SHALL serialise as JSON `null`, never as omitted keys.

#### Scenario: Todo payload includes tags and parent links

- **WHEN** `get-tasks(view="today")` returns a task that has tags `["@computer", "high-energy"]` and belongs to project `"Q2 Planning"`
- **THEN** the corresponding `data[i]` object has `tags: ["@computer", "high-energy"]`
- **AND** `data[i].project` is the project's UUID
- **AND** `data[i].project_title` is `"Q2 Planning"`

#### Scenario: Detail view enriches checklists

- **WHEN** `get-project(uuid="ABC-123")` returns a project whose tasks contain a Todo with three checklist items
- **THEN** that Todo's `checklist` field is a list of three `ChecklistItem` objects
- **AND** each `ChecklistItem` has a `title` and a `status` of `"open"` or `"completed"`

#### Scenario: List view populates dates and status

- **WHEN** `get-tasks(view="upcoming")` returns a task with a deadline of `2026-05-01` and status `"incomplete"`
- **THEN** `data[i].deadline` is the string `"2026-05-01"`
- **AND** `data[i].status` is `"incomplete"`
- **AND** `data[i].type` is `"to-do"`

#### Scenario: Missing optional fields serialise as null

- **WHEN** a tool returns a Todo that has no notes and no deadline
- **THEN** the Todo's `notes` field is JSON `null` (not omitted)
- **AND** the Todo's `deadline` field is JSON `null` (not omitted)

### Requirement: Tools SHALL also emit a backwards-compatible TextContent block

Every `ToolResult` returned by a tool MUST include exactly one `TextContent` entry in `content`. The text body MUST be produced by a `render_*` helper in `formatters.py` (or an equivalent per-tool renderer) and MUST contain the same human-readable fields the tool emitted before this change. Tools MUST NOT rely on FastMCP's auto-derived text block (which serialises raw JSON).

#### Scenario: Text block preserves prior formatting

- **WHEN** a client that ignores `structured_content` calls `get-tasks(view="today")`
- **THEN** the `TextContent` body contains lines starting with `"Title:"`, `"UUID:"`, `"Status:"`, and (when applicable) `"Tags:"`, `"Deadline:"`, `"Project:"`, `"Area:"`, and `"Checklist:"`
- **AND** the body matches the byte-for-byte output of the prior `format_todo` helper for that input

#### Scenario: focus-mode preserves the focus banner

- **WHEN** a client calls `focus-mode` and the server selects an overdue task
- **THEN** the `TextContent` body begins with `"**FOCUS:`
- **AND** the prose continues with the rendered Todo

### Requirement: Bulk tools SHALL report per-item success and failure

Bulk tools (`bulk-capture`, `bulk-complete`, `bulk-cancel`, `bulk-modify`, `bulk-triage`) SHALL return `data` of type `BulkResult` containing `requested`, `succeeded`, `failed`, `succeeded_ids`, `failed_ids`, `errors`, and (for `bulk-triage`) `by_action`. The `errors` array MUST contain one `BulkItemError` per failure with `task_id` (or `null` for batch-level failures), `action`, and human-readable `reason`. Aggregate counts (`succeeded`, `failed`) MUST equal the sum of per-item outcomes plus any batch-level failure counts.

#### Scenario: bulk-complete reports which IDs failed

- **WHEN** a client calls `bulk-complete(task_ids=[A, B, C])` and tasks A and C succeed but B fails
- **THEN** `data.requested == 3`
- **AND** `data.succeeded == 2`
- **AND** `data.failed == 1`
- **AND** `data.succeeded_ids == ["A", "C"]`
- **AND** `data.failed_ids == ["B"]`
- **AND** `data.errors` contains one entry with `task_id == "B"`, `action == "complete"`, and a non-empty `reason`

#### Scenario: bulk-triage groups counts by action

- **WHEN** a client calls `bulk-triage` with 4 complete + 2 defer + 1 delegate decisions and all succeed
- **THEN** `data.by_action == {"complete": 4, "defer": 2, "delegate": 1}`
- **AND** `data.succeeded == 7`
- **AND** `data.failed == 0`

### Requirement: tools/list SHALL advertise an outputSchema for every tool

For every registered tool, the `tools/list` response SHALL include an `outputSchema` field whose value is a JSON Schema describing that tool's `ToolEnvelope` (with the tool-specific `data` type). Tools registered without an explicit `output_schema=` argument on the `@mcp.tool(...)` decorator SHALL be considered a configuration error and SHALL fail a startup audit test.

#### Scenario: Every tool advertises an output schema

- **WHEN** a client issues a `tools/list` request
- **THEN** every entry in the response's `tools` array has a non-null `outputSchema`
- **AND** each `outputSchema` validates as JSON Schema draft 2020-12
- **AND** each `outputSchema` describes an object with `data`, `summary`, `meta` properties

#### Scenario: Startup audit catches missing output_schema

- **WHEN** the server starts up
- **THEN** an audit step iterates over registered tools
- **AND** any tool whose advertised `outputSchema` is null causes the audit to fail loudly (test or log error)

### Requirement: ChatGPT strict-mode transforms SHALL apply to output schemas

The `ClientCompatibilityMiddleware.on_list_tools` hook SHALL apply the same strict-mode transforms it currently applies to input schemas — `additionalProperties: false`, nullable-type expansion (`{type: "string", nullable: true}` → `{type: ["string", "null"]}`), and recursive `anyOf`/`oneOf` flattening — to every tool's `outputSchema` whenever the request's `User-Agent` matches a ChatGPT identifier. The `anyOf` flattener SHALL recurse into `properties`, `items`, `additionalProperties`, and `$defs`. Non-ChatGPT clients SHALL receive the un-transformed Pydantic-emitted schema.

#### Scenario: ChatGPT receives strict output schemas

- **WHEN** a client with `User-Agent: ChatGPT/...` calls `tools/list`
- **THEN** every `outputSchema` returned has `additionalProperties: false` at every object level
- **AND** no `outputSchema` contains an `anyOf` or `oneOf` keyword (including inside `$defs`)
- **AND** every nullable field uses `type: [..., "null"]` rather than `nullable: true` or `anyOf` with a `null` branch

#### Scenario: Non-ChatGPT client receives raw Pydantic schemas

- **WHEN** a client with a non-ChatGPT `User-Agent` (e.g. n8n, Claude Desktop) calls `tools/list`
- **THEN** `outputSchema` for tools with optional fields MAY contain `anyOf` (Pydantic's default `Optional[X]` representation)
- **AND** the schema does not need `additionalProperties: false` enforcement

#### Scenario: anyOf flattener handles nested $defs

- **WHEN** the strict-mode transform processes an `outputSchema` whose `data` is `Project` with nested `$defs.Todo` containing `Optional` fields
- **THEN** every `anyOf` inside `$defs.Todo` is flattened to `type: [..., "null"]`
- **AND** the resulting schema validates as JSON Schema draft 2020-12 with `additionalProperties: false` everywhere
