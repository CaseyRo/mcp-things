## Context

The server currently has 21 tools organized by GTD stage across four modules. Project/area tooling is limited: `plan-project` creates projects, `create-area` creates areas, `get-projects`/`get-areas` list all items, and `convert-to-project` promotes tasks. There is no single-item retrieval, no project modification tool (despite `url_scheme.update_project()` existing), no area modification, and no area deletion or merging.

Testing confirmed these AppleScript/Things behaviors:

- `set area of project to targetArea` — works
- `move todo to targetArea` — works
- `move project to targetArea` — works
- `delete area` — works, but **trashes loose to-dos** and orphans projects
- `set area of project to missing value` — **fails** (can't unset area)

## Goals / Non-Goals

**Goals:**

- Single-item retrieval: `get-project`, `get-area` with name/UUID resolution
- Project modification: `modify-project` wrapping the existing `update_project` URL scheme
- Area modification: `modify-area` via AppleScript (rename, tags)
- Safe area deletion: `delete-area` with loose to-do guard
- Area merging: `merge-areas` that relocates all contents before deleting source
- Enhance `plan-project` (notes, checklist) and `create-area` (initial projects)

**Non-Goals:**

- Bulk project operations (batch complete/cancel)
- Project reordering within areas
- Area reordering
- Moving projects between areas as a standalone tool (not needed — `modify-project` with `area` param covers this via URL scheme `area-id`)
- Undo/rollback for area deletion

## Decisions

### 1. Module placement: read-only utility vs. write organize

**Decision:** Read tools (`get-project`, `get-area`) go in `tools_utility.py`. Write tools (`modify-project`, `modify-area`, `delete-area`, `merge-areas`) go in `tools_gtd_organize.py`. This keeps `tools_utility.py` as a read-only module (its current invariant — zero write tools) and groups all write operations in Organize alongside `modify-task`, `plan-project`, `create-area`.

**Rationale:** `modify-project` was initially planned for `tools_utility.py`, but that would break the read-only invariant and require importing write-operation patterns (`url_scheme`, `applescript_bridge`, `triage_tracker`). All other modification tools live in Organize. `tools_gtd_organize.py` will grow to ~1100 lines — acceptable given cohesion. If it exceeds that, area lifecycle tools (`create-area`, `modify-area`, `delete-area`, `merge-areas`) can be split into `tools_area_lifecycle.py` as a post-implementation refactor.

**Alternative considered:** Dedicated CRUD modules. Rejected because it breaks the GTD-stage organization pattern. Also considered keeping `modify-project` in utility — rejected because it would be the only write tool there.

### 2. Name-to-UUID resolution — new `resolvers.py` module

**Decision:** Extract `_resolve_list_id()` from `tools_gtd_organize.py` into a new `resolvers.py` module with two public functions: `resolve_list_id()` (existing logic) and `resolve_item()` (returns full item dict). Both tool modules import from `resolvers.py`.

**Rationale:** Currently no tool module imports another — this is a good invariant. If `_resolve_list_id` stayed in `tools_gtd_organize.py` and `tools_utility.py` imported it, we'd create a cross-dependency. A dedicated ~50-line `resolvers.py` is clean, testable in isolation, and depends only on `things` (third-party) and `ToolError` (FastMCP). `resolve_item()` returns the full object for `get-project`/`get-area` use cases.

**Alternative considered:** Putting `_resolve_item()` in `tools_utility.py` and cross-importing `_resolve_list_id` from Organize. Rejected because it violates the no-cross-import invariant.

### 3. `delete-area` safety: hard error on loose to-dos

**Decision:** `delete-area` always runs a dry-run scan first. If any loose to-dos exist (to-dos in the area not belonging to a project), it raises a ToolError listing them and refuses to proceed. If only projects remain, it warns they'll become area-less and proceeds.

**Rationale:** Things trashes loose to-dos on area deletion — this is destructive and not recoverable via the API. Projects survive as area-less, which is benign. The user can use `merge-areas` as the safe alternative, or manually move/complete/cancel to-dos first.

### 4. `merge-areas` operation order

**Decision:** Move all items in this order: (1) loose to-dos via `move todo to targetArea`, (2) projects via `move project to targetArea`, (3) delete source area. Each move is individual AppleScript calls.

**Rationale:** Moving to-dos first ensures they're safe before any deletion. Individual AppleScript calls (not batch) because Things AppleScript doesn't support batch `move` on heterogeneous item types. If any move fails, the operation stops and reports partial progress — the source area is only deleted when fully empty.

**Alternative considered:** Using URL scheme `update` to set list-id on each to-do. Rejected because URL scheme can't move to-dos to an area (only to a project), while AppleScript `move` handles both.

### 5. `modify-area` via AppleScript (not URL scheme)

**Decision:** Area modifications (rename, tags) use AppleScript `set name of area to "..."` and `set tag names of area to "..."`. There is no Things URL scheme for area updates.

**Rationale:** Things provides `update-project` URL scheme but nothing equivalent for areas. AppleScript is the only programmatic interface for area mutations. This is consistent with how `create-area` already works.

### 6. `modify-project` via URL scheme (including area reassignment)

**Decision:** `modify-project` wraps `url_scheme.update_project()` plus a new `area_id` parameter. Testing confirmed that `things:///update-project?id=<uuid>&area-id=<area-uuid>` successfully moves a project to a different area. The `update_project()` function needs a new `area_id` parameter added.

**Rationale:** The URL scheme builder already handles most parameters. Area reassignment via `area-id` was tested and confirmed working (not documented in official Things URL scheme docs but functional). This closes the gap where `delete-area` creates area-less projects but there was no tool to fix them — `modify-project(area=...)` is now the answer.

**Alternative considered:** AppleScript `move project to area`. Works but unnecessary since URL scheme handles it. Keeping everything in URL scheme is more consistent with the rest of `modify-project`.

### 7. Cache invalidation strategy

**Decision:** Follow existing patterns:

- Read tools (`get-project`, `get-area`): Use `@cached(ttl=CACHE_TTL.get("operation", 30))`
- Write tools: Call `invalidate_caches_for([...])` after mutations
- `modify-project`: invalidate `get-projects`, `get-tasks`
- `modify-area`, `delete-area`, `merge-areas`: invalidate `get-areas`, `get-projects`, `get-tasks`

### 8. Tool annotations

**Decision:** All new tools get entries in `TOOL_ANNOTATIONS` dict following existing patterns:

- Read tools: `readOnlyHint=True`, `openWorldHint=False`
- Write tools: `readOnlyHint=False`, `destructiveHint=True` for delete/merge, `False` for modify

### 9. GTD layer integration (existing tool updates)

These changes address gaps identified by UX audit where existing GTD workflow tools need awareness of the new CRUD capabilities:

**`weekly-review`** — Add "Area-less Projects" section after stalled-projects. Query `things.projects()` filtered by `project.get("area") is None`. Only render when list is non-empty. Prompt user to use `modify-project(area=...)`.

**`convert-to-project`** — Append to success message: "Use `modify-project` to assign an area, set a deadline, or edit properties." When source task had no area, additionally note the project is area-less.

**`process-inbox`** — Add fourth branch to decision tree: "Is this a next action for an existing project? → Use `schedule-task` with `project=` to add it directly."

**`daily-review`** — Add project-level overdue scan alongside existing task overdue scan. Query `things.projects()` filtered by `project.get("deadline") < today`. Show as separate "Overdue Projects" subsection.

**Rationale:** The new CRUD tools create states (area-less projects, projects with editable deadlines) that existing GTD workflow tools need to surface. Without these updates, `delete-area` silently creates orphans that `weekly-review` never catches, and `convert-to-project` gives users no path to post-conversion editing.

### 10. Documentation updates

**Decision:** Update all project documentation to reflect the expanded tool set and auth requirements.

**CLAUDE.md updates needed:**

- Architecture section: tool count 21 → 27, add new tools to the tool organization table
- Tool Organization by GTD Stage: add `modify-project` to Organize, `get-project`/`get-area` to Utility, `modify-area`/`delete-area`/`merge-areas` to Organize
- Environment Variables: clarify `THINGS_AUTH_TOKEN` is required for all new write tools (`modify-project`, `modify-area`, `delete-area`, `merge-areas`, enhanced `create-area`, enhanced `plan-project`)
- `THINGS_MCP_API_KEY` section: note that all new tools require Bearer auth like existing tools

**README.md updates needed:**

- Line 150: Tool count "21" → "27"
- GTD Tools tables: add `modify-project` and `create-area` enhancements to Organize, add `get-project`/`get-area` to a new section or Utility, add `modify-area`/`delete-area`/`merge-areas` to Organize
- Reflect table: update `daily-review` description to mention overdue projects, `weekly-review` to mention area-less projects
- Line 192: Update "Plus..." list to include new tools
- Removed Tools table line 329: `update-project` replacement should reference `modify-project` (not `modify-task`)
- Authentication section: note that all write tools (including new CRUD tools) require `THINGS_AUTH_TOKEN` for Things app access

**Rationale:** New users discovering the server need to know that write operations require both `THINGS_AUTH_TOKEN` (Things app auth) and `THINGS_MCP_API_KEY` (MCP client auth). The current docs only mention this in passing — with 6 new write-capable tools, it should be prominent.

### 11. Security hardening (from security audit)

**AppleScript injection prevention:** All AppleScript tools that look up an area/project MUST resolve name → UUID via `things.areas()`/`things.projects()` (SQLite, safe) first, then use `whose id is "<uuid>"` in AppleScript. Never interpolate user-supplied names as AppleScript lookup tokens. UUIDs are alphanumeric+hyphens (validated by `THINGS_UUID_PATTERN`) and safe to interpolate directly.

**TOCTOU guards:** `delete-area` and `merge-areas` MUST re-read area contents immediately before the `delete area` AppleScript call. If the re-read shows items that shouldn't be there, abort. This closes the window between dry-run/move and deletion.

**Control character stripping:** Extend `escape_applescript_string()` to strip `[\x00-\x1f\x7f]` before escaping quotes. Newlines/null bytes in user input could break AppleScript structure.

**Input length limits:** Add `validate_name()` in `input_validation.py` — max 255 chars for names, max 10,000 for notes. Call on all text inputs in new tools.

**Self-merge UUID comparison:** `merge-areas` self-merge check MUST compare resolved UUIDs, not input strings. A user could bypass string comparison by providing name for one and UUID for the other.

### 12. GTD methodology alignment

Based on deep research into David Allen's published methodology:

**"Canceled" is not GTD terminology.** Allen's system has three project states: active (has next action), incubated (Someday/Maybe), or removed. The complete/cancel distinction is a Things 3 feature. Tool docstrings MUST frame these as Things 3 operations, not GTD concepts.

**Daily review is not a GTD ritual.** Allen prescribes informal daily engagement (check calendar, work from context lists), not a structured review. Our `daily-review` tool is a convenience feature, not GTD methodology.

**Clarify vs. Organize separation.** Allen's Clarify flowchart does NOT include "is this part of an existing project?" — that is an Organize concern. Our `process-inbox` enhancement should be labeled as organize-stage guidance, visually separated from the clarify decision tree.

**Weekly review does not check project-to-area alignment.** Area of Focus review is a separate higher-horizon exercise. Our "Unassigned Projects" section in `weekly-review` is a tool feature, not GTD. Language changed from "orphaned" to "unassigned" to avoid implying projects require areas.

**Projects don't require areas.** In GTD, a project without an area of focus is a signal to review during higher-horizon planning, not an error state.

## Risks / Trade-offs

**[AppleScript race conditions]** → Moving many items in `merge-areas` involves sequential AppleScript calls. If Things is busy or slow, individual moves could fail. **Mitigation:** Check each move result, stop on first failure, report which items were moved and which weren't. Source area is only deleted after all moves succeed.

**[No area unset]** → AppleScript can't set area to `missing value`. This means `delete-area` (projects-only case) leaves projects area-less. However, `modify-project(area=...)` can reassign them to a new area via URL scheme `area-id`. **Mitigation:** `weekly-review` surfaces area-less projects and points to `modify-project`. The only gap is truly "unsetting" an area (making a project area-less on purpose), which is an edge case.

**[Name ambiguity]** → Multiple projects/areas could share the same name (Things allows this). **Mitigation:** Reuse existing `_resolve_list_id` pattern that returns all matches with UUIDs when ambiguous, letting the user pick.

**[URL scheme fire-and-forget]** → `modify-project` via URL scheme has no response — we assume success. **Mitigation:** This is the same pattern used by all existing write tools (`capture-task`, `schedule-task`, etc.). Cache invalidation after the call ensures the next read reflects changes.
