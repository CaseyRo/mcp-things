## 1. Quick Wins (N+1 fixes, cleanup)

- [x] 1.1 Fix `format_todo` N+1: use `project_title`/`area_title` from things-py dict, fall back to `things.get()` only when absent
- [x] 1.2 Fix `format_project` N+1: same pattern for area title resolution
- [x] 1.3 Fix `weekly-review` N+1: replace per-project `things.todos(project=uuid)` loop with single `things.todos(status="incomplete")` + Python group-by
- [x] 1.4 Rewrite `merge-areas` to use single AppleScript block with internal UUID loop instead of per-item subprocess calls
- [x] 1.5 Remove or update stale `validate_tool_registration` in `utils.py`

## 2. Benchmark Harness (Phase 0)

- [x] 2.1 Create `scripts/benchmark.py` CLI with `--output markdown` and `--output json` flags
- [x] 2.2 Implement standard suite: inbox read, single task get, search, modify, capture (5 iterations each)
- [x] 2.3 Add cold vs. warm call separation (first call labeled cold)
- [x] 2.4 Add osascript subprocess timing instrumentation (separate from end-to-end)
- [x] 2.5 Add task count scaling measurement for `get-tasks`
- [x] 2.6 Run benchmark against live server and document baseline numbers in CDI-708 comment

## 3. Batch Tools (Phase 1)

- [x] 3.1 Create `src/things_mcp/tools_batch.py` module with registration function
- [x] 3.2 Define `CaptureItem` Pydantic model (title, notes, when, tags, deadline) for typed LLM schema
- [x] 3.3 Define `TriageDecision` Pydantic model with `model_validator` enforcing co-field requirements (when for defer/schedule, delegated_to for delegate, project for assign)
- [x] 3.4 Add UUID format validation helper to `input_validation.py`
- [x] 3.5 Implement `bulk-capture` using `execute_json()` with `build_todo_object()` (JSON URL scheme, max 50 items)
- [x] 3.6 Implement `bulk-complete` using single AppleScript with UUID loop (max 50, UUID validated)
- [x] 3.7 Implement `bulk-cancel` using single AppleScript with UUID loop (max 50, UUID validated)
- [x] 3.8 Implement `bulk-modify` for uniform changes (when, add_tags, project, area) via AppleScript; call `ensure_tags_exist()` for add_tags; validate project/area mutual exclusivity
- [x] 3.9 Implement `bulk-triage` composite tool: group decisions by action type, route to appropriate mechanism; action="assign" routes to convert-to-project (without first_action)
- [x] 3.10 Add tool annotations for all batch tools in `tool_annotations.py`; document `bulk-*` prefix convention in module docstring
- [x] 3.11 Register batch tools in `fast_server.py`
- [x] 3.12 Write unit tests for batch tools (mock AppleScript/URL scheme)

## 4. Tool Ergonomics

- [x] 4.1 Add `all: bool = False` and `limit: int = 50` parameters to `process-inbox`; all=True returns compact list format with shared GTD decision tree once at top
- [x] 4.2 Add `when` optional parameter to `capture-task`
- [x] 4.3 Add `task_title` fallback to `defer-task` (matching `complete-task` pattern)
- [x] 4.4 Add `task_title` fallback to `delegate-task`
- [x] 4.5 Add `task_title` fallback to `modify-task`
- [x] 4.6 Add `limit` parameter to `get-tasks` (default 50, max 200) with "more results" indicator
- [x] 4.7 Add `limit` parameter to `search-tasks` (default 20), document cap in docstring

## 5. Integration Testing & Benchmark Re-run

- [x] 5.1 Run full test suite (`pytest tests -m "not real"`) to verify no regressions
- [x] 5.2 Run real integration tests with Things 3 for batch tools
- [x] 5.3 Re-run benchmark to measure before/after improvement
- [x] 5.4 Update CLAUDE.md tool count and architecture docs

## 6. SQLite Read Layer (Phase 3)

- [x] 6.1 Create `src/things_mcp/sqlite_reader.py` with read-only WAL-compatible connection
- [x] 6.2 Implement schema version detection and validation on startup
- [x] 6.3 Implement core read queries: inbox, today, upcoming, anytime, someday, todos with filters
- [x] 6.4 Implement search query with title/notes matching
- [x] 6.5 Add graceful fallback to things-py when SQLite is locked or missing
- [x] 6.6 Migrate `get-tasks`, `search-tasks`, `daily-review`, `weekly-review`, `focus-mode` to SQLite reader
- [x] 6.7 Migrate `process-inbox`, `get-project`, `get-area`, `triage-insights` to SQLite reader
- [x] 6.8 Re-run benchmark to validate <100ms target for 200+ task reads
