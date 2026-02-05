# GTD Tools Specification Delta

## REMOVED Requirements

### Requirement: Deprecated Read Tool Aliases

**Reason**: Replaced by `get-tasks` with `list_filter` parameter
**Migration**: Use `get-tasks` with appropriate filter value

The following CRUD-style aliases are removed:

- `get-inbox` → `get-tasks(list_filter="inbox")`
- `get-today` → `get-tasks(list_filter="today")`
- `get-upcoming` → `get-tasks(list_filter="upcoming")`
- `get-anytime` → `get-tasks(list_filter="anytime")`
- `get-someday` → `get-tasks(list_filter="someday")`
- `get-logbook` → `get-tasks(list_filter="logbook")`
- `get-trash` → `get-tasks(list_filter="trash")`
- `get-todos` → `get-tasks()`
- `get-tagged-items` → `get-tasks(tag="tag-name")`
- `get-recent` → `get-tasks(list_filter="logbook")`

#### Scenario: User calls removed tool

- **WHEN** a client calls `get-inbox` or other removed tool
- **THEN** the MCP server returns "tool not found" error

### Requirement: Deprecated Search Tool Aliases

**Reason**: Replaced by unified `search-tasks` tool
**Migration**: Use `search-tasks` with query parameter

The following search aliases are removed:

- `search-todos`
- `search-advanced`
- `search-items`

#### Scenario: User calls removed search tool

- **WHEN** a client calls `search-todos` or other removed search tool
- **THEN** the MCP server returns "tool not found" error

### Requirement: Deprecated Write Tool Aliases

**Reason**: Replaced by GTD-aligned tools that encourage proper workflow
**Migration**: Use GTD tools based on intent

The following CRUD-style write tools are removed:

- `add-todo` → use `capture-task` (quick capture) or `schedule-task` (with scheduling)
- `add-project` → use `plan-project`
- `update-todo` → use `modify-task`
- `update-project` → use `modify-task`

#### Scenario: User calls removed write tool

- **WHEN** a client calls `add-todo` or other removed write tool
- **THEN** the MCP server returns "tool not found" error

### Requirement: Deprecated UI Tool Aliases

**Reason**: Replaced by `show-in-app` utility tool
**Migration**: Use `show-in-app` with item_id parameter

The following UI tool is removed:

- `show-item` → use `show-in-app`

#### Scenario: User calls removed UI tool

- **WHEN** a client calls `show-item`
- **THEN** the MCP server returns "tool not found" error

## ADDED Requirements

### Requirement: Tool Migration Documentation

The system SHALL provide clear migration documentation for users of deprecated tools.

#### Scenario: User needs to migrate from deprecated tools

- **WHEN** a user consults the CHANGELOG or README
- **THEN** they find a complete mapping table from old tool names to new GTD tools

#### Scenario: README includes removed tools section

- **WHEN** a user reads the README.md
- **THEN** they find a "Removed Tools" section at the end documenting what was removed and why
