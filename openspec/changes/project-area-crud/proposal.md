## Why

Projects and areas are core GTD containers, but our MCP tooling only covers basic creation and listing. There's no way to update a project (rename, reschedule, add notes), complete/cancel a project, modify an area, or get details on a single project/area by name or UUID. The `update_project` URL scheme builder already exists but isn't exposed as a tool. This gap forces users to open Things manually for routine project/area management.

## What Changes

- **New tool: `modify-project`** — Update project title, notes, schedule, deadline, tags, area, or mark complete/canceled. Wraps the existing `url_scheme.update_project()` plus new `area-id` param (tested, works).
- **New tool: `modify-area`** — Rename an area or update its tags via AppleScript (no URL scheme exists for area updates).
- **New tool: `delete-area`** — Remove an area. Runs dry-run first showing contents. **Refuses to delete if loose to-dos exist** (Things trashes them on area deletion — unsafe). Only proceeds when the area contains just projects (which safely become area-less) or is empty. User must move/complete/cancel loose to-dos first.
- **New tool: `merge-areas`** — Move all projects and loose to-dos from a source area into a target area, then delete the now-empty source. Safe path for "two areas converge" scenario — loose to-dos are reassigned before deletion so nothing gets trashed.
- **New tool: `get-project`** — Get a single project by name or UUID with full detail (notes, tasks, deadline, area).
- **New tool: `get-area`** — Get a single area by name or UUID with its projects and tasks.
- **Enhanced: `create-area`** — Accept optional initial projects list to seed an area on creation.
- **Enhanced: `plan-project`** — Accept optional notes and checklist items (currently only supports title + tasks + deadline + tags + area).
- **Updated: `convert-to-project`** — Success message now guides to `modify-project` for post-conversion editing.
- **Updated: `process-inbox`** — Decision tree adds "existing project" branch via `schedule-task(project=...)`.
- **Updated: `weekly-review`** — New "Area-less Projects" section surfaces orphaned projects from `delete-area`.
- **Updated: `daily-review`** — New "Overdue Projects" section catches project-level deadline misses.

## Capabilities

### New Capabilities

- `project-crud`: Full project lifecycle — get single project, modify project properties, complete/cancel projects
- `area-crud`: Full area lifecycle — get single area, modify area properties (rename, tags), delete area (with orphan reporting), merge two areas

### Modified Capabilities

_(No existing specs are changing at the requirement level)_

## Impact

- **New file**: `resolvers.py` (~50 lines) — extracted name-to-UUID resolution, used by both tool modules
- **Modified files**: `tools_gtd_organize.py` (all write tools: `modify-project`, `modify-area`, `delete-area`, `merge-areas`, enhanced `plan-project`, `create-area`), `tools_utility.py` (read-only: `get-project`, `get-area`), `tools_gtd_core.py` (convert-to-project guidance, process-inbox branch), `tools_gtd_reflect.py` (weekly-review unassigned section, daily-review overdue projects), `tool_annotations.py` (new entries), `url_scheme.py` (add `area_id` to `update_project`), `applescript_bridge.py` (control char stripping), `input_validation.py` (name validation)
- **URL scheme**: `update_project` gets `area-id` param (tested, works); area modifications need AppleScript (no URL scheme)
- **Tool count**: 21 → 27 (6 new tools)
- **Cache**: New tools need `@cached` decorators and cache invalidation on writes
- **Documentation**: Update CLAUDE.md architecture section (new tool count, tool list), environment variables section (auth requirements for new write tools), client compatibility notes. Update README if it exists.
- **No breaking changes** — all additions are net-new or backward-compatible enhancements
- **Things behavior constraint**: Deleting an area trashes loose to-dos but orphans projects. AppleScript cannot unset an area (set to "no area") — only reassign to a different area. `merge-areas` works around this; `delete-area` guards against it.
