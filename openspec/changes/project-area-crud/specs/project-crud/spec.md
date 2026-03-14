## ADDED Requirements

### Requirement: Get single project by name or UUID

The system SHALL provide a `get-project` tool that retrieves a single project with full detail (title, notes, tasks, deadline, tags, area, status, creation/modification dates). The tool SHALL accept a project name or UUID as input. When given a name, the system SHALL perform case-insensitive matching.

#### Scenario: Get project by exact name

- **WHEN** user calls `get-project` with a name matching an existing project
- **THEN** system returns the project with all fields: title, notes, tasks (with their status), deadline, tags, area, and status

#### Scenario: Get project by UUID

- **WHEN** user calls `get-project` with a valid project UUID
- **THEN** system returns the project with full detail

#### Scenario: Project not found

- **WHEN** user calls `get-project` with a name or UUID that matches no project
- **THEN** system raises a ToolError with a descriptive message

#### Scenario: Ambiguous name match

- **WHEN** user calls `get-project` with a name that matches multiple projects (case-insensitive)
- **THEN** system returns a bulleted disambiguation list with each match's title, UUID, area, and status (matching the format used by `complete-task`)

### Requirement: Modify project properties

The system SHALL provide a `modify-project` tool that updates project properties via the existing `url_scheme.update_project()`. All parameters except the project identifier SHALL be optional. The tool SHALL accept project name or UUID as the identifier. The tool SHALL support an `area` parameter that reassigns the project to a different area via the `area-id` URL scheme parameter.

#### Scenario: Rename a project

- **WHEN** user calls `modify-project` with a new title
- **THEN** system updates the project title via URL scheme and invalidates relevant caches

#### Scenario: Update project notes

- **WHEN** user calls `modify-project` with `notes`, `prepend_notes`, or `append_notes`
- **THEN** system updates the project notes accordingly (replace, prepend, or append)

#### Scenario: Reschedule project

- **WHEN** user calls `modify-project` with `when` and/or `deadline`
- **THEN** system updates the project schedule and/or deadline

#### Scenario: Update project tags

- **WHEN** user calls `modify-project` with `tags` or `add_tags`
- **THEN** system ensures tags exist (via `ensure_tags_exist`), then updates the project tags

#### Scenario: Complete a project

- **WHEN** user calls `modify-project` with `completed=true`
- **THEN** system marks the project as completed via URL scheme (Things 3 feature — GTD simply removes projects from the active list when the outcome is achieved)

#### Scenario: Cancel a project

- **WHEN** user calls `modify-project` with `canceled=true`
- **THEN** system marks the project as canceled via URL scheme (Things 3 feature — in GTD, a project you decide not to pursue is either moved to Someday/Maybe or removed entirely)

#### Scenario: Reassign project to area

- **WHEN** user calls `modify-project` with `area` (name or UUID)
- **THEN** system resolves the area name to UUID, then updates the project via `area-id` URL scheme parameter, and invalidates area/project caches

#### Scenario: Complete project with incomplete tasks

- **WHEN** user calls `modify-project` with `completed=true` on a project that has incomplete tasks
- **THEN** system completes the project and includes a note in the response: "Note: this project had N incomplete tasks which are now also completed"

#### Scenario: Project not found

- **WHEN** user calls `modify-project` with a name or UUID matching no project
- **THEN** system raises a ToolError

#### Scenario: Resolve name to UUID

- **WHEN** user calls `modify-project` with a project name (not UUID)
- **THEN** system resolves the name to a UUID using `_resolve_list_id` before calling the URL scheme

### Requirement: Enhanced plan-project accepts notes and checklist items

The existing `plan-project` tool SHALL accept optional `notes` and `checklist` parameters. Notes SHALL be passed through to `add_project_with_tasks()`. Checklist items SHALL be set on the project itself (not as child tasks).

#### Scenario: Create project with notes

- **WHEN** user calls `plan-project` with a `notes` parameter
- **THEN** system creates the project with the provided notes

#### Scenario: Create project with checklist

- **WHEN** user calls `plan-project` with a `checklist` parameter (list of strings)
- **THEN** system creates the project with checklist items attached to the project heading

### Requirement: convert-to-project post-conversion guidance

The `convert-to-project` tool's success message SHALL include a hint about `modify-project` for post-conversion editing (area assignment, deadline, notes). This is especially important when the source task had no area, as the new project will be area-less.

#### Scenario: Conversion success message includes guidance

- **WHEN** `convert-to-project` completes successfully
- **THEN** the response includes: "Use `modify-project` to assign an area, set a deadline, or edit properties."

#### Scenario: Converted from inbox task (no area)

- **WHEN** `convert-to-project` completes on a task that had no area
- **THEN** the response additionally notes: "This project has no area — consider assigning one with `modify-project`."

### Requirement: process-inbox includes organize-stage guidance for existing projects

After the Clarify decision tree completes (actionable → not 2-min → defer), the `process-inbox` output SHALL include an Organize hint: "If this is a next action for an existing project, use `schedule-task` with `project=` to add it directly." This is Organize-stage guidance (not part of Allen's Clarify flowchart) and SHALL be visually separated from the Clarify decision tree.

#### Scenario: Organize guidance after decision tree

- **WHEN** `process-inbox` displays the decision tree and the item is actionable
- **THEN** the output includes organize-stage guidance for adding to an existing project via `schedule-task(project=...)`, clearly labeled as an organizing step

### Requirement: weekly-review surfaces unassigned projects

The `weekly-review` tool SHALL check for projects with no area of focus assigned. If any exist, it SHALL display them in an "Unassigned Projects" section after the stalled-projects section. This is a tool-level organizational aid (Allen's weekly review does not check project-to-area alignment — area review is a separate higher-horizon exercise). The section SHALL prompt the user to assign an area via `modify-project(area=...)` or accept them as intentionally unassigned.

#### Scenario: Unassigned projects exist

- **WHEN** `weekly-review` runs and there are incomplete projects with no area
- **THEN** the output includes an "Unassigned Projects" section listing them with a prompt to use `modify-project(area=...)` or acknowledge as intentionally unassigned

#### Scenario: No unassigned projects

- **WHEN** `weekly-review` runs and all incomplete projects have areas (or there are no projects)
- **THEN** the "Unassigned Projects" section is omitted

### Requirement: Tool docstrings include GTD "Use when" guidance

All new retrieval tools (`get-project`, `get-area`) and modification tools (`modify-project`, `modify-area`) SHALL include explicit "Use when:" lines in their docstrings to help LLMs select the right tool. `get-project`: "Use when you need full detail on a specific project or its UUID." `get-area`: "Use when inspecting a specific area before modifying or deleting it."

#### Scenario: LLM tool selection

- **WHEN** an LLM reads the tool list to decide between `get-projects` (list all) and `get-project` (single)
- **THEN** the docstring clearly differentiates: `get-project` is for targeted single-item lookup, `get-projects` is for listing all
