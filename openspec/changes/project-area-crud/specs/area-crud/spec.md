## ADDED Requirements

### Requirement: Get single area by name or UUID

The system SHALL provide a `get-area` tool that retrieves a single area with full detail (name, tags, projects list, loose to-do count). The tool SHALL accept an area name or UUID. Name matching SHALL be case-insensitive.

#### Scenario: Get area by name

- **WHEN** user calls `get-area` with a name matching an existing area
- **THEN** system returns the area with: name, tags, list of projects (with status), and count of loose to-dos

#### Scenario: Get area by UUID

- **WHEN** user calls `get-area` with a valid area UUID
- **THEN** system returns the area with full detail

#### Scenario: Area not found

- **WHEN** user calls `get-area` with a name or UUID that matches no area
- **THEN** system raises a ToolError with a descriptive message

#### Scenario: Ambiguous name match

- **WHEN** user calls `get-area` with a name that matches multiple areas (case-insensitive)
- **THEN** system returns a bulleted disambiguation list with each match's name, UUID, project count, and to-do count

#### Scenario: Include items flag

- **WHEN** user calls `get-area` with `include_items=true`
- **THEN** system returns the area with full project details and individual loose to-do listings

### Requirement: Modify area properties

The system SHALL provide a `modify-area` tool that renames an area or updates its tags via AppleScript. The tool SHALL accept area name or UUID as the identifier. All AppleScript lookups SHALL use UUID (`whose id is "<uuid>"`) — never user-supplied names as lookup tokens. Name-to-UUID resolution SHALL happen via `things.areas()` (SQLite read) before any AppleScript construction.

#### Scenario: Rename an area

- **WHEN** user calls `modify-area` with a new `name`
- **THEN** system validates the new name is not empty/whitespace-only and does not exceed 255 characters, resolves the area to UUID, then renames via AppleScript `set name of (first area whose id is "<uuid>") to "<escaped-name>"` and invalidates area caches

#### Scenario: Rename to duplicate name

- **WHEN** user calls `modify-area` with a name that already exists (case-insensitive)
- **THEN** system raises a ToolError indicating the name is taken

#### Scenario: Update area tags

- **WHEN** user calls `modify-area` with `tags`
- **THEN** system ensures tags exist and updates the area's tags via AppleScript

#### Scenario: Area not found

- **WHEN** user calls `modify-area` with a name or UUID matching no area
- **THEN** system raises a ToolError

### Requirement: Delete area with safety guard

The system SHALL provide a `delete-area` tool that removes an area. The tool SHALL always perform a dry-run first, listing the area's contents (projects and loose to-dos). The tool SHALL refuse to delete if the area contains any loose to-dos, because Things trashes loose to-dos on area deletion. Immediately before the `delete area` AppleScript call, the tool SHALL re-check the area contents via `things.todos(area=uuid)` to guard against TOCTOU — if new to-dos appeared since the dry-run, it SHALL abort. All AppleScript lookups SHALL use UUID, not user-supplied names.

#### Scenario: Delete empty area

- **WHEN** user calls `delete-area` on an area with no projects and no loose to-dos
- **THEN** system deletes the area via AppleScript and invalidates caches

#### Scenario: Delete area with only projects

- **WHEN** user calls `delete-area` on an area containing projects but no loose to-dos
- **THEN** system reports which projects will become area-less, then deletes the area

#### Scenario: Delete area with loose to-dos (blocked)

- **WHEN** user calls `delete-area` on an area containing loose to-dos
- **THEN** system raises a ToolError listing the loose to-dos with a primary recommendation: "Use `merge-areas` to move everything to another area first, then delete." Secondary alternatives: move to-dos into a project, complete them, or cancel them

#### Scenario: Area not found

- **WHEN** user calls `delete-area` with a name or UUID matching no area
- **THEN** system raises a ToolError

### Requirement: Merge two areas

The system SHALL provide a `merge-areas` tool that moves all contents (projects and loose to-dos) from a source area into a target area, then deletes the now-empty source. This SHALL use AppleScript `move` for both to-dos and projects. The tool SHALL report what was moved. Before deleting the source area, the tool SHALL re-read the source area's contents to confirm it is empty (guards against silent move failures). All AppleScript lookups SHALL use UUID. The self-merge check SHALL compare resolved UUIDs, not user-supplied input strings.

#### Scenario: Merge areas with mixed contents

- **WHEN** user calls `merge-areas` with source and target area names
- **THEN** system moves all projects from source to target via `move project to targetArea`, moves all loose to-dos from source to target via `move todo to targetArea`, deletes the empty source area, and returns a summary of moved items

#### Scenario: Merge into self

- **WHEN** user calls `merge-areas` where source and target resolve to the same UUID (even if provided as name vs UUID)
- **THEN** system raises a ToolError

#### Scenario: Source area empty

- **WHEN** user calls `merge-areas` on a source area with no contents
- **THEN** system deletes the empty source area and reports nothing was moved

#### Scenario: Partial move failure

- **WHEN** a move operation fails mid-merge (AppleScript error on one item)
- **THEN** system stops and raises a ToolError that includes: (1) count and names of items successfully moved to target, (2) count and names of items still in source, (3) instruction that re-running `merge-areas` is safe because already-moved items are in the target and won't be moved again

#### Scenario: Source or target not found

- **WHEN** user calls `merge-areas` with a source or target name/UUID that doesn't exist
- **THEN** system raises a ToolError identifying which area was not found

### Requirement: Enhanced create-area accepts initial projects

The existing `create-area` tool SHALL accept an optional `projects` parameter (list of project names). When provided, the system SHALL create the area first, then create each project within that area.

#### Scenario: Create area with initial projects

- **WHEN** user calls `create-area` with `name` and `projects=["Project A", "Project B"]`
- **THEN** system creates the area, then creates each project assigned to that area, and the success message includes a warning: "These projects have no tasks yet — they will appear as stalled in weekly review until you add next actions."

#### Scenario: Create area without projects (existing behavior)

- **WHEN** user calls `create-area` with only `name` (and optional `tags`)
- **THEN** system creates the area exactly as it does today (no regression)
