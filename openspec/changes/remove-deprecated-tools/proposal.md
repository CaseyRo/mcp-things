# Change: Remove Deprecated Tool Aliases

## Why

The codebase currently has 18 deprecated tool aliases in `tools_deprecated.py` that duplicate functionality provided by the GTD-native tools. These aliases:
- Add 300+ lines of code with only 29% test coverage
- Confuse users with multiple ways to do the same thing
- Increase maintenance burden
- Were intended as temporary backward-compatibility shims

The GTD-native tools (`capture-task`, `get-tasks`, `schedule-task`, etc.) are now stable and well-tested. It's time to remove the legacy CRUD-style aliases.

## What Changes

**BREAKING**: The following tools will be removed:

### Read Operations (replaced by `get-tasks` with filters)
- `get-inbox` → use `get-tasks` with `list_filter="inbox"`
- `get-today` → use `get-tasks` with `list_filter="today"`
- `get-upcoming` → use `get-tasks` with `list_filter="upcoming"`
- `get-anytime` → use `get-tasks` with `list_filter="anytime"`
- `get-someday` → use `get-tasks` with `list_filter="someday"`
- `get-logbook` → use `get-tasks` with `list_filter="logbook"`
- `get-trash` → use `get-tasks` with `list_filter="trash"`
- `get-todos` → use `get-tasks`
- `get-tagged-items` → use `get-tasks` with `tag` parameter
- `get-recent` → use `get-tasks` with `list_filter="logbook"`

### Search Operations (replaced by `search-tasks`)
- `search-todos` → use `search-tasks`
- `search-advanced` → use `search-tasks`
- `search-items` → use `search-tasks`

### Write Operations (replaced by GTD tools)
- `add-todo` → use `capture-task` or `schedule-task`
- `add-project` → use `plan-project`
- `update-todo` → use `modify-task`
- `update-project` → use `modify-task`

### UI Operations (replaced by `show-in-app`)
- `show-item` → use `show-in-app`

## Impact

- **Affected code**: `src/things_mcp/tools_deprecated.py` (entire file removed)
- **Affected code**: `src/things_mcp/tool_annotations.py` (remove deprecated annotations)
- **Affected code**: `src/things_mcp/fast_server.py` (remove import/registration)
- **Affected tests**: `tests/test_gtd_workflow.py` (may need migration path tests)
- **Breaking for**: Users calling deprecated tool names directly
- **Migration**: Document mapping in CHANGELOG and README
