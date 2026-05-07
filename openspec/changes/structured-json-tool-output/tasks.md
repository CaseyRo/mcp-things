## 1. Models module

- [x] 1.1 Create `src/things_mcp/models.py` with `ToolEnvelope` (generic over `DataT`), `ChecklistItem`, `Todo`, `Project`, `Area`, `Tag`, `WriteResult`, `BulkItemError`, `BulkResult`, `FocusResult`, `ReviewReport`, `TriageInsightsModel`, `CacheStats`, `ShowInAppResult`.
- [x] 1.2 Add a helper `output_schema_for(envelope_cls)` that returns `envelope_cls.model_json_schema(mode="serialization")` and runs it through `_strict_transform_schema(...)` so `output_schema=` callers get a single one-liner.
- [x] 1.3 Unit tests: every model round-trips `model_dump(mode="json")` → `model_validate_json` losslessly; `output_schema_for(ToolEnvelope[Todo])` is valid JSON Schema draft 2020-12; `additionalProperties: false` everywhere; no `anyOf`/`oneOf` survives in the strict-mode form (including nested `$defs`).

## 2. Formatter split

- [x] 2.1 In `src/things_mcp/formatters.py`, add `to_dict_todo(row) -> dict`, `to_dict_project(row, include_items=False)`, `to_dict_area(row, include_items=False)`, `to_dict_tag(row, include_items=False)` returning data shaped to the Pydantic models.
- [x] 2.2 Add `render_todo`, `render_project`, `render_area`, `render_tag` that produce the byte-identical text the existing `format_*` helpers produce (move existing logic; do not change the strings).
- [x] 2.3 Keep `format_*` names as thin shims that call `render_*` so unmigrated callers stay green.
- [x] 2.4 Unit tests: `render_*(row) == format_*(row)` for a snapshot fixture set covering Todo with/without notes, tags, checklist, project, area, deadline; Project with/without items; Area with/without items; Tag with/without shortcut. *(verified: all 27 existing `test_formatters.py` tests pass against the shimmed `format_*` names byte-for-byte.)*

## 3. ToolResult helper + return-shape utilities

- [x] 3.1 Add `src/things_mcp/tool_results.py` with `make_result(data, summary, meta=None, text=None)` returning `ToolResult(content=[TextContent(type="text", text=text or summary)], structured_content=ToolEnvelope(data=data, summary=summary, meta=meta or {}).model_dump(mode="json"))`.
- [x] 3.2 Provide convenience builders: `write_result(thing_id=None, summary, meta=None, text=None)` and `bulk_result(requested, succeeded_ids, failed_ids, errors, by_action=None, summary, text=None)`.
- [x] 3.3 Unit tests: `make_result` produces a `ToolResult` whose `structured_content` validates against `ToolEnvelope`; `text` defaults to `summary` when omitted; explicit `text` overrides.

## 4. Migrate utility tools

- [x] 4.1 `get-cache-stats` → `data: CacheStats`, `output_schema=output_schema_for(ToolEnvelope[CacheStats])`.
- [x] 4.2 `show-in-app` → `data: ShowInAppResult`.
- [x] 4.3 `get-tags` → `data: list[Tag]`.
- [x] 4.4 `get-areas` → `data: list[Area]` (no item enrichment).
- [x] 4.5 `get-area` (single) → `data: Area` enriched with `projects` and `tasks` (project-less direct todos).
- [x] 4.6 `get-projects` → `data: list[Project]` (no task enrichment).
- [x] 4.7 `get-project` (single) → `data: Project` enriched with `tasks`; each Todo enriched with `checklist` via `db.checklist_items(uuid)`.
- [x] 4.8 `search-tasks` → `data: list[Todo]` (no checklist enrichment).
- [x] 4.9 `triage-insights` → `data: TriageInsights`.
- [x] 4.10 Unit tests per tool: existing assertions in `test_project_area_crud.py` and `test_tools_unit.py` migrated to `tool_text(result)` helper in `conftest.py`; full suite (430 tests) green.

## 5. Migrate Engage / Capture / Clarify tools

- [x] 5.1 `get-tasks` → `data: list[Todo]`; `meta.total_count` and `meta.truncated` populated when sliced; tags / dates / parent links populated; checklist NOT included (list view). *(CDI-1021 must-have; structured shape and truncation covered by `TestGetTasks::test_structured_content_*` in `tests/test_tools_unit.py`.)*
- [x] 5.2 `focus-mode` → `data: FocusResult` (Todo + `selection_reason: Literal["overdue", "today_with_deadline", "today", "anytime"]`); checklist enriched (detail view).
- [x] 5.3 `complete-task` → `data: WriteResult` with `thing_id` populated and `summary == "Task completed successfully. Keep up the momentum!"` for parity.
- [x] 5.4 `capture-task` → `data: WriteResult` (`thing_id` typically null because URL scheme returns no UUID).
- [x] 5.5 `process-inbox` (single mode) → `data: Todo` enriched with checklist; `meta.remaining` carries the count of remaining inbox items; the GTD decision tree stays in `TextContent` only.
- [x] 5.6 `process-inbox(all=true)` → `data: list[Todo]` (no checklist enrichment); `meta.total_count`, `meta.truncated`.
- [x] 5.7 `convert-to-project` → `data: WriteResult` with the new project's UUID where derivable. *(thing_id is null — JSON-API doesn't expose the new project's UUID.)*
- [x] 5.8 Unit tests per tool: enrichment fields populated where required; text snapshots preserved; ToolError still raised on failure paths.

## 6. Migrate Organize tools

- [x] 6.1 `schedule-task`, `defer-task`, `delegate-task`, `modify-task` → `data: WriteResult`.
- [x] 6.2 `plan-project`, `modify-project`, `create-area`, `modify-area`, `delete-area`, `merge-areas` → `data: WriteResult`.
- [x] 6.3 Unit tests: `acknowledged: true` path on URL-scheme success; ToolError on resolver failures.

## 7. Migrate Reflect tools

- [x] 7.1 `daily-review` → `data: ReviewReport` with `today_tasks`, `overdue`, `completed_today`, `inbox_count`, `summary`.
- [x] 7.2 `weekly-review` → `data: ReviewReport` with weekly fields.
- [x] 7.3 Unit tests: structured payload contains the same items the prose currently lists.

## 8. Migrate batch tools to BulkResult

- [x] 8.1 `bulk-capture` → `data: BulkResult`; per-item `succeeded_ids` from JSON-API response (best effort: list of titles when UUIDs unavailable).
- [x] 8.2 `bulk-complete` → `data: BulkResult` (AppleScript failures fall through `ToolError` so the whole call surfaces as MCP `isError`).
- [x] 8.3 `bulk-cancel` → same shape as `bulk-complete`.
- [x] 8.4 `bulk-modify` → `data: BulkResult` with per-task URL-scheme outcome (each failure becomes a `BulkItemError(task_id, action="modify", reason=...)`).
- [x] 8.5 `bulk-triage` → `data: BulkResult` with `by_action` populated; AppleScript-batch failures expand into per-item `BulkItemError` entries; URL-scheme failures become per-item errors with the originating action.
- [x] 8.6 Unit tests per bulk tool: structured envelope shape, `succeeded_ids`/`failed_ids`/`errors`/`by_action` correct on success and failure paths.

## 9. Output-schema strict-mode middleware

- [x] 9.1 In `src/things_mcp/server_core.py`, extend `ClientCompatibilityMiddleware.on_list_tools` to traverse `tool.output_schema` (when present) and apply the existing input-schema transforms.
- [x] 9.2 Upgrade the `anyOf`/`oneOf` flattener to recurse into `properties`, `items`, `additionalProperties`, and `$defs`.
- [x] 9.3 Apply ChatGPT strict-mode (`additionalProperties: false`, nullable-type expansion) to output schemas only when `User-Agent` matches the ChatGPT detector that already exists.
- [x] 9.4 Unit tests:
  - feed `output_schema_for(ToolEnvelope[Project])` (which has nested `$defs.Todo` with optionals) through the transform; assert no `anyOf`/`oneOf` survives anywhere, including inside `$defs`;
  - assert `additionalProperties: false` is set on every object node;
  - assert non-ChatGPT path's flattener still produces valid JSON Schema.

## 10. Server-level audit + integration tests

- [x] 10.1 Pytest test (`tests/test_structured_output.py::test_every_tool_publishes_an_output_schema`) iterates `await mcp.list_tools()` and asserts every tool has a non-null `output_schema`. Failure mode names the offending tool.
- [x] 10.2 Integration test (`tests/test_structured_output.py::test_get_tasks_structured_content_validates_against_envelope`, `not real`): asserts `get-tasks` `structuredContent` validates against `ToolEnvelope[list[Todo]]` and the tool's declared `outputSchema`.
- [x] 10.3 Integration test for ChatGPT `User-Agent` (`test_chatgpt_user_agent_strips_anyof_from_output_schemas`): asserts no `anyOf`/`oneOf` survives anywhere (including `$defs`) and every transformed schema remains a valid Draft 2020-12 schema.
- [x] 10.4 Integration test for n8n `User-Agent` (`test_n8n_user_agent_keeps_schemas_valid_and_nullable`): schemas remain valid; nullable output fields accept null payloads.

## 11. Documentation

- [x] 11.1 Updated `CLAUDE.md` "Key Patterns" section: documents the `ToolEnvelope` contract, the `make_result`/`write_result`/`bulk_result` helpers, and the `output_schema=` requirement on every `@mcp.tool`. Domain-model overview added.
- [x] 11.2 Updated `CLAUDE.md` "Client Compatibility Middleware" section: notes that `on_list_tools` also transforms `outputSchema` and that the `anyOf` flattener recurses into `$defs`.
- [x] 11.3 Added a "Tool response shape" section to `README.md` with the envelope shape and a one-paragraph migration note for downstream consumers.

## 12. Cleanup

- [x] 12.1 Removed the `format_*` shims; `tests/test_formatters.py` now imports `render_*` directly. Production code (`tools_*`) was already on `render_*`.
- [x] 12.2 `ruff check .` clean; `ruff format .` applied.
- [x] 12.3 `uv run python -m pytest tests` → 438 passed, 14 skipped, 36 deselected (CI-safe default). `-m real` deferred to local macOS with Things 3.
- [x] 12.4 `openspec validate structured-json-tool-output --strict` clean.
