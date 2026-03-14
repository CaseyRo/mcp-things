## 1. Security Hardening (prerequisites)

- [x] 1.1 Extend `escape_applescript_string()` in `applescript_bridge.py` — strip control characters `[\x00-\x1f\x7f]` before escaping quotes
- [x] 1.2 Add `validate_name()` to `input_validation.py` — reject empty/whitespace-only, enforce max 255 chars for names; add `MAX_NOTES_LENGTH=10000` validation
- [x] 1.3 Add `"name"` to `SENSITIVE_FIELDS` in `logging_config.py` (or document convention that area/project names log as `"title"` key)

## 2. URL Scheme Foundation

- [x] 2.1 Add `area_id` parameter to `url_scheme.update_project()` — add `area_id: Optional[str] = None` param, include `"area-id": area_id` in params dict
- [x] 2.2 Add tool annotation entries in `tool_annotations.py` for all 6 new tools: `get-project`, `get-area`, `modify-project`, `modify-area`, `delete-area`, `merge-areas`

## 3. Name Resolution — new `resolvers.py`

- [x] 3.1 Create `src/things_mcp/resolvers.py` (~50 lines) with two public functions: `resolve_list_id(name_or_uuid, list_type) -> str` (extracted from `tools_gtd_organize.py`) and `resolve_item(name_or_uuid, item_type) -> dict` (new, returns full item for get-project/get-area); depends only on `things` and `ToolError`
- [x] 3.2 Update `tools_gtd_organize.py` to import `resolve_list_id` from `resolvers` instead of using private `_resolve_list_id()`; remove the private function

## 4. Read Tools (tools_utility.py — stays read-only)

- [x] 4.1 Implement `get-project` tool — accept name/UUID, return full detail (title, notes, tasks with status, deadline, tags, area, status, dates); use `resolve_item()` from `resolvers.py`; include "Use when:" in docstring
- [x] 4.2 Implement `get-area` tool — accept name/UUID, return name/tags/projects list/loose to-do count; `include_items` flag for full detail; ambiguous name disambiguation; "Use when:" docstring; ensure return value is never logged (contains PII)

## 5. Write Tools (tools_gtd_organize.py — all writes stay in Organize)

- [x] 5.1 Implement `modify-project` tool — accept name/UUID + optional title, notes, prepend_notes, append_notes, when, deadline, tags, add_tags, area, completed, canceled; resolve name to UUID via `resolvers.resolve_list_id()`; resolve area name to UUID for `area-id` (validate UUID format before URL scheme); call `url_scheme.update_project()`; warn on completing project with incomplete tasks; invalidate caches; GTD-accurate docstring: frame complete/cancel as Things 3 features (not GTD terminology)
- [x] 5.2 Implement `modify-area` tool — resolve name→UUID via `resolvers.resolve_list_id()` first; validate new name (not empty, max 255 chars, not duplicate); AppleScript uses `whose id is "<uuid>"` for lookup (NEVER user-supplied name as lookup token); `set name`/`set tag names`; invalidate caches
- [x] 5.3 Implement `delete-area` tool — resolve to UUID; dry-run scan (list projects + loose to-dos); hard error if loose to-dos exist (lead with `merge-areas` recommendation); re-check area contents via `things.todos(area=uuid)` immediately before `delete` AppleScript (TOCTOU guard); abort if new items appeared; AppleScript uses `whose id is "<uuid>"`; invalidate caches
- [x] 5.4 Implement `merge-areas` tool — resolve source + target to UUIDs via `resolvers.resolve_list_id()`; self-merge guard compares UUIDs (not input strings); move to-dos first (`move todo to targetArea`), then projects; track moved items; on partial failure: stop, report moved/remaining, note re-run is safe; re-read source area before deletion to confirm empty; delete source; invalidate caches

## 6. Enhanced Existing Tools

- [x] 6.1 Enhance `plan-project` — add optional `notes` and `checklist` parameters; pass notes to `add_project_with_tasks()`; pass checklist items to project; validate notes length
- [x] 6.2 Enhance `create-area` — add optional `projects` parameter (list of names); validate each name; after area creation, create each project in that area; success message warns: "These projects have no tasks yet — they will appear as stalled in weekly review until you add next actions (GTD: every project needs a next action)."

## 7. GTD Layer Integration

- [x] 7.1 Update `convert-to-project` success message — append `modify-project` guidance; when source task had no area, add: "This project has no area of focus — consider assigning one with `modify-project`."
- [x] 7.2 Update `process-inbox` — after the Clarify decision tree, add organize-stage guidance (visually separated): "If this is a next action for an existing project, use `schedule-task` with `project=` to add it directly." Label as Organize guidance, not Clarify (Allen's Clarify flowchart does not include this branch)
- [x] 7.3 Update `weekly-review` — add "Unassigned Projects" section after stalled-projects; query `things.projects()` filtered by no area; only render when non-empty; prompt `modify-project(area=...)` or accept as intentionally unassigned; note this is a tool feature (Allen's weekly review does not check project-to-area alignment)
- [x] 7.4 Update `daily-review` — add "Overdue Projects" subsection; query `things.projects()` filtered by deadline < today; separate from overdue tasks; note this is a convenience feature (GTD does not prescribe a formal daily review)

## 8. Documentation

- [x] 8.1 Update `CLAUDE.md` — architecture section: tool count 21→27, add new tools to Tool Organization table (Organize: `modify-project`, `modify-area`, `delete-area`, `merge-areas`; Utility: `get-project`, `get-area`)
- [x] 8.2 Update `CLAUDE.md` — environment variables: clarify `THINGS_AUTH_TOKEN` required for all write tools (including new CRUD tools), `THINGS_MCP_API_KEY` required for all MCP client connections
- [x] 8.3 Update `README.md` — tool count "21" → "27"; add new tools to GTD Tools tables; update Reflect descriptions (weekly-review: unassigned projects; daily-review: overdue projects)
- [x] 8.4 Update `README.md` — fix Removed Tools table: `update-project` replacement should reference `modify-project` (not `modify-task`); update "Plus..." list
- [x] 8.5 Update `README.md` — Authentication section: clarify both `THINGS_AUTH_TOKEN` (Things app access for writes) and `THINGS_MCP_API_KEY` (MCP client bearer token) are required

## 9. Tests

- [x] 9.1 Add unit tests for `get-project` — by name, by UUID, not found, ambiguous match disambiguation format
- [x] 9.2 Add unit tests for `modify-project` — rename, area reassignment (UUID validation), complete with incomplete tasks warning, not found
- [x] 9.3 Add unit tests for `get-area` — by name, by UUID, not found, ambiguous, include_items
- [x] 9.4 Add unit tests for `modify-area` — rename (UUID-based lookup), duplicate name guard, empty name rejection, tags, not found
- [x] 9.5 Add unit tests for `delete-area` — empty area, projects-only, blocked by loose to-dos (error leads with merge-areas), TOCTOU re-check behavior
- [x] 9.6 Add unit tests for `merge-areas` — mixed contents, self-merge guard (UUID comparison, not string), partial failure reporting, empty source, re-read before delete
- [x] 9.7 Add unit tests for enhanced `plan-project` (notes, checklist) and `create-area` (projects param, stalled warning)
- [x] 9.8 Add unit tests for GTD integration: `convert-to-project` guidance message, `process-inbox` organize-stage guidance, `weekly-review` unassigned projects section, `daily-review` overdue projects
- [x] 9.9 Add security tests: `escape_applescript_string()` strips control chars; `validate_name()` rejects empty/long/control-char names; AppleScript injection attempt in area name is neutralized by UUID lookup
- [x] 9.10 Add real integration tests (marker: `real`) for `get-project`, `modify-project`, `get-area`, `modify-area`, `delete-area`, `merge-areas` using `MCP-TEST-` prefix items
- [x] 9.11 Verify `url_scheme.update_project()` `area_id` parameter generates correct URL
