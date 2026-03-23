## ADDED Requirements

### Requirement: bulk-capture creates multiple inbox items in one call

The system SHALL provide a `bulk-capture` tool that accepts a typed list of `CaptureItem` objects and creates them all via a single Things JSON URL scheme call.

`CaptureItem` schema:

- `title: str` (required)
- `notes: Optional[str]`
- `when: Optional[Literal["today", "tomorrow", "evening", "anytime", "someday"]]`
- `tags: Optional[list[str]]`
- `deadline: Optional[str]` (YYYY-MM-DD)

The tool also accepts `default_when` which applies to items without an explicit `when` value. Items with their own `when` take precedence. Maximum 50 items per call.

#### Scenario: Capture 5 items from a meeting

- **WHEN** `bulk-capture` is called with 5 `CaptureItem` objects each having title and optional notes/tags
- **THEN** all 5 items appear in Things inbox
- **THEN** only 1 URL open and 1 sleep cycle occurs (not 5)
- **THEN** the response reports how many items were captured

#### Scenario: Capture with per-item and default scheduling

- **WHEN** `bulk-capture` is called with `default_when="today"` and some items override with their own `when` value
- **THEN** items without a `when` value use the default
- **THEN** items with a `when` value use their override

#### Scenario: Duplicate titles are allowed

- **WHEN** `bulk-capture` is called with two items having the same title
- **THEN** both items are created as separate tasks (Things allows duplicates)

#### Scenario: Validation rejects empty list

- **WHEN** `bulk-capture` is called with an empty task list
- **THEN** a ToolError is raised with a descriptive message

#### Scenario: Validation rejects oversized list

- **WHEN** `bulk-capture` is called with more than 50 items
- **THEN** a ToolError is raised advising to split into multiple calls

### Requirement: bulk-complete marks multiple tasks complete in one call

The system SHALL provide a `bulk-complete` tool that accepts a list of task UUIDs (max 50) and completes them all via a single AppleScript execution. Each UUID SHALL be validated against UUID format before embedding in AppleScript.

#### Scenario: Complete 3 tasks

- **WHEN** `bulk-complete` is called with 3 valid task UUIDs
- **THEN** all 3 tasks are marked complete in Things
- **THEN** only 1 `run_applescript()` subprocess call occurs (not 3)
- **THEN** the response includes the titles of completed tasks

#### Scenario: UUID format validation

- **WHEN** `bulk-complete` is called with a non-UUID string in `task_ids`
- **THEN** a ToolError is raised before any AppleScript execution

#### Scenario: Partial failure reporting

- **WHEN** `bulk-complete` is called and AppleScript fails mid-loop
- **THEN** the error message reports how many tasks were processed before failure
- **THEN** the error message includes the UUIDs of remaining unprocessed tasks

### Requirement: bulk-cancel cancels multiple tasks in one call

The system SHALL provide a `bulk-cancel` tool with the same shape, validation, and behavior as `bulk-complete` but setting status to canceled.

#### Scenario: Cancel 4 tasks

- **WHEN** `bulk-cancel` is called with 4 valid task UUIDs
- **THEN** all 4 tasks are marked canceled in Things via a single AppleScript execution

### Requirement: bulk-modify applies uniform changes to multiple tasks

The system SHALL provide a `bulk-modify` tool that applies the same modification to all specified tasks (max 50). UUID format validation SHALL be applied. Tags SHALL be created via `ensure_tags_exist()` before applying. `project` and `area` are mutually exclusive — providing both SHALL raise a ToolError.

#### Scenario: Move tasks to a project

- **WHEN** `bulk-modify` is called with 5 task UUIDs and `project="Project Name"`
- **THEN** all 5 tasks are moved to the specified project

#### Scenario: Add tags to multiple tasks

- **WHEN** `bulk-modify` is called with task UUIDs and `add_tags=["@computer"]`
- **THEN** `ensure_tags_exist(["@computer"])` is called first
- **THEN** all specified tasks have the `@computer` tag added

#### Scenario: Reschedule multiple tasks

- **WHEN** `bulk-modify` is called with task UUIDs and `when="tomorrow"`
- **THEN** all specified tasks are rescheduled to tomorrow

#### Scenario: Mutual exclusivity of project and area

- **WHEN** `bulk-modify` is called with both `project` and `area` specified
- **THEN** a ToolError is raised explaining they are mutually exclusive

### Requirement: bulk-triage processes multiple inbox decisions in one call

The system SHALL provide a `bulk-triage` tool that accepts a typed list of `TriageDecision` objects and executes them all, grouping by action type for efficiency.

`TriageDecision` schema (Pydantic model with `model_validator`):

- `task_id: str` (required, UUID format validated)
- `action: Literal["complete", "cancel", "defer", "schedule", "delegate", "assign"]` (required)
- `when: Optional[str]` — REQUIRED when action is `defer` or `schedule`
- `delegated_to: Optional[str]` — REQUIRED when action is `delegate`
- `project: Optional[str]` — REQUIRED when action is `assign`
- `notes: Optional[str]`

The `model_validator` SHALL enforce co-field requirements and raise a `ValueError` with a specific message if required fields are missing for the given action.

Note on action `assign`: this routes to `convert-to-project` logic. The `first_action` parameter of `convert-to-project` is NOT supported in bulk-triage — the LLM should use `convert-to-project` directly if `first_action` is needed.

Performance note: `complete` and `cancel` actions are grouped into single AppleScript calls (O(1) subprocess). `defer`, `schedule`, and `delegate` actions each require a separate URL scheme call with a 0.5–0.7s sleep (O(N) URL opens but only 1 MCP round-trip). A 20-item triage is 1 MCP call replacing 40 MCP calls, but defer/schedule items still incur individual URL scheme sleeps.

#### Scenario: Full inbox triage

- **WHEN** `bulk-triage` is called with 20 decisions (mix of complete, cancel, defer, schedule, delegate)
- **THEN** completions and cancellations are grouped into single AppleScript calls
- **THEN** deferrals and schedules use URL scheme calls (one per item)
- **THEN** the response reports per-action counts and any failures

#### Scenario: Co-field validation

- **WHEN** a triage decision includes `action="defer"` without a `when` value
- **THEN** validation fails with "'when' is required for action='defer'"

#### Scenario: Per-task decision for deferral

- **WHEN** a triage decision includes `action="defer"` with `when="next-week"`
- **THEN** the task is deferred to next week via the existing `defer-task` logic

#### Scenario: Per-task decision for delegation

- **WHEN** a triage decision includes `action="delegate"` with `delegated_to="Alice"`
- **THEN** the task is delegated using the existing `delegate-task` logic

#### Scenario: Per-task decision for project assignment

- **WHEN** a triage decision includes `action="assign"` with `project="My Project"`
- **THEN** the task is converted to a project via `convert-to-project` logic (without first_action)

#### Scenario: Non-inbox task IDs accepted

- **WHEN** `bulk-triage` is called with task UUIDs that are not in the inbox
- **THEN** the actions are executed (the tool is optimized for inbox but not restricted to it)

### Requirement: process-inbox supports returning all items

The system SHALL add an optional `all` parameter to `process-inbox` that returns all inbox items (up to `limit`, default 50) in a compact format with a single shared GTD decision tree.

#### Scenario: Default behavior unchanged

- **WHEN** `process-inbox` is called without `all` parameter
- **THEN** only the oldest inbox item is returned with full GTD decision tree (existing behavior)

#### Scenario: All items mode with compact format

- **WHEN** `process-inbox(all=True)` is called
- **THEN** the response includes a shared GTD decision tree once at the top
- **THEN** each item is listed compactly: title, UUID, notes preview, tags
- **THEN** the LLM can then call `bulk-triage` with decisions for all items

#### Scenario: All items mode respects limit

- **WHEN** `process-inbox(all=True)` is called and inbox has 200 items
- **THEN** at most 50 items are returned (or custom `limit` value)
- **THEN** the response indicates total inbox count and how many are shown

### Requirement: capture-task supports optional scheduling

The system SHALL add an optional `when` parameter to `capture-task` to avoid the capture-then-schedule two-step.

#### Scenario: Capture with schedule

- **WHEN** `capture-task` is called with `title="Call Alex"` and `when="tomorrow"`
- **THEN** the task is created and scheduled for tomorrow in one call

#### Scenario: Capture without schedule (default)

- **WHEN** `capture-task` is called with only a title
- **THEN** the task goes to inbox as before (no behavior change)

### Requirement: Task tools support title-based lookup

The tools `defer-task`, `delegate-task`, and `modify-task` SHALL accept an optional `task_title` parameter as an alternative to `task_id`, matching the pattern already in `complete-task`.

#### Scenario: Defer by title

- **WHEN** `defer-task` is called with `task_title="Call Alex"` instead of `task_id`
- **THEN** the system searches for matching tasks
- **THEN** if exactly one match, it proceeds with the deferral
- **THEN** if multiple matches, it returns the list for disambiguation

### Requirement: get-tasks supports result limiting

The system SHALL add a `limit` parameter to `get-tasks` with a default of 50 and maximum of 200.

#### Scenario: Default limit

- **WHEN** `get-tasks` is called without a `limit` parameter
- **THEN** at most 50 tasks are returned
- **THEN** the response indicates if more tasks exist beyond the limit

#### Scenario: Custom limit

- **WHEN** `get-tasks(limit=100)` is called
- **THEN** at most 100 tasks are returned

### Requirement: search-tasks documents and exposes result cap

The system SHALL add a `limit` parameter to `search-tasks` (defaulting to 20) and document the cap in the tool description.

#### Scenario: Default cap visible in response

- **WHEN** `search-tasks` returns results truncated at the limit
- **THEN** the response states how many total results exist and how many are shown

### Requirement: format_todo avoids N+1 queries

The `format_todo` function SHALL use `project_title` and `area_title` fields from the things-py todo dict when available, falling back to `things.get()` only when those fields are absent.

#### Scenario: Todo with project_title present

- **WHEN** `format_todo` is called with a todo dict containing `project_title`
- **THEN** it uses `project_title` directly without calling `things.get()`

#### Scenario: Todo with project UUID but no project_title

- **WHEN** `format_todo` is called with a todo dict containing `project` UUID but no `project_title`
- **THEN** it falls back to `things.get(project_uuid)` to resolve the title

### Requirement: weekly-review uses single query for stalled project detection

The `weekly-review` tool SHALL detect stalled projects using a single `things.todos(status="incomplete")` call with Python-side grouping, replacing the per-project query loop.

#### Scenario: 30 active projects

- **WHEN** `weekly-review` runs with 30 active projects
- **THEN** it makes 1 query for all incomplete todos (not 30 separate queries)
- **THEN** it groups results by project UUID in Python to detect stalled projects

### Requirement: merge-areas uses single AppleScript block

The `merge-areas` tool SHALL move all items using a single AppleScript execution with an internal loop, replacing the per-item subprocess call pattern.

#### Scenario: Merge area with 10 todos and 5 projects

- **WHEN** `merge-areas` is called for a source area with 10 todos and 5 projects
- **THEN** 1 AppleScript subprocess is spawned (not 15)
- **THEN** partial failure is still detected and reported

### Requirement: Stale validate_tool_registration is removed

The `validate_tool_registration` function in `utils.py` SHALL be removed or updated to reflect the current 27-tool surface.

#### Scenario: Cleanup

- **WHEN** the codebase is inspected
- **THEN** `validate_tool_registration` either references the current tool names or is deleted if unused in production code
