# Changelog

## [2.1.14] - 2026-08-26

- fix(formatters): carry reminder_time through to_dict projections (CDI-1543)


## [2.1.13] - 2026-07-11

- Bump fastmcp 3.4.3->3.4.4


## [2.1.12] - 2026-07-08

- Pin Python 3.12.11: TCC AppleEvents grants are keyed to the interpreter binary; 3.13 venv hangs osascript under launchd


## [2.1.11] - 2026-07-08

- openspec: reference consolidated cdit store


## [2.1.10] - 2026-07-08

- fix: fastmcp>=3.4.3 + allowed_hosts=["*"] — 3.4.3 rejects non-localhost Host with 421 (edge CF-Access/Tailscale gated)


## [2.1.9] - 2026-06-30

- chore(deps): security upgrades (pip-audit)


## [2.1.8] - 2026-06-30

- docs: hygiene pass — fix clone path, document batch tools, sanitize infra refs


## [2.1.6] - 2026-06-10

- fix(things): harden ToolEnvelope (optional summary, extra=ignore) (shelf) (#36)


## [2.1.5] - 2026-06-10

- ci: bump GitHub Actions to node24 majors (checkout@v6, setup-python@v6) (#35)


## [2.1.4] - 2026-06-10

- feat: fastmcp 3.4.2 uplift — annotations, structured output, resources, prompts, context (#34)


## [2.1.3] - 2026-06-05

- chore(ci): drop PyPI publishing — deploy is launchd-local, no PyPI consumers (CDI-1169)


## [2.1.2] - 2026-06-05

- fix(ci): dispatch publish.yml after tag push so PyPI publish fires (CDI-1169)


All notable changes to Things 3 Enhanced MCP will be documented in this file.

## [Unreleased]

### Fixed

- `modify-task` can now clear an existing deadline or start date (`when`).
  Pass a clear-sentinel — `none`, `clear`, `remove`, or `null`
  (case-insensitive) — for `deadline`/`when`. This enables moving an overdue
  task to Someday and dropping its stale deadline in one call
  (`when="someday"`, `deadline="none"`). Empty string also clears at the URL
  layer, but a non-empty sentinel is the documented contract because some
  MCP clients/middleware drop empty optional params. (CDI-1167)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-04-09

### Changed

- Bumped FastMCP dependency to >=3.2.2
- `get_tasks` view parameter now uses Literal enum for type safety
- Improved `complete_task` docstring to clarify identification requirements

### Added

- Automated version bump and release CI via GitHub Actions

## [Unreleased]

### BREAKING CHANGES

- **Removed 18 deprecated tool aliases** - Legacy CRUD-style tools removed in favor of GTD-native tools
  - **Migration guide:**

    | Removed Tool | Replacement |
    |--------------|-------------|
    | `get-inbox` | `get-tasks(list_filter="inbox")` |
    | `get-today` | `get-tasks(list_filter="today")` |
    | `get-upcoming` | `get-tasks(list_filter="upcoming")` |
    | `get-anytime` | `get-tasks(list_filter="anytime")` |
    | `get-someday` | `get-tasks(list_filter="someday")` |
    | `get-logbook` | `get-tasks(list_filter="logbook")` |
    | `get-trash` | `get-tasks(list_filter="trash")` |
    | `get-todos` | `get-tasks()` |
    | `get-tagged-items` | `get-tasks(tag="tag-name")` |
    | `get-recent` | `get-tasks(list_filter="logbook")` |
    | `search-todos` | `search-tasks` |
    | `search-advanced` | `search-tasks` |
    | `search-items` | `search-tasks` |
    | `add-todo` | `capture-task` or `schedule-task` |
    | `add-project` | `plan-project` |
    | `update-todo` | `modify-task` |
    | `update-project` | `modify-task` |
    | `show-item` | `show-in-app` |

- **Removed SSE transport support** - SSE transport is deprecated in MCP protocol (2025-03-26)
  - Removed `/sse/` endpoint - all clients now use `/mcp` (streamable-http transport)
  - Transport configuration simplified: `THINGS_MCP_TRANSPORT` now only accepts `"streamable-http"` (default)
  - **Migration**: Update `THINGS_MCP_TRANSPORT` from `"both"` or `"sse"` to `"streamable-http"` or remove it to use default
  - ChatGPT, Claude Desktop, and n8n all use streamable-http transport via `/mcp` endpoint

### Changed

- **Split server into GTD-aligned modules** - Major refactoring for maintainability:
  - `fast_server.py` reduced from 2,404 lines to 111 lines (entry point only)
  - New `server_core.py` - Server factory, n8n middleware, schema patches
  - New `tool_annotations.py` - Shared tool annotations dictionary
  - New `tools_gtd_core.py` - GTD Engage/Capture/Clarify tools (6 tools)
  - New `tools_gtd_organize.py` - GTD Organize stage tools (5 tools)
  - New `tools_gtd_reflect.py` - GTD Reflect stage tools (2 tools)
  - New `tools_utility.py` - Utility tools (6 tools)
  - Each module now has focused responsibility, easier to test and maintain

### Added

- **THINGS_MCP_DEBUG environment variable** - Enable verbose console logging for debugging
  - When `false` (default): Console shows INFO level only
  - When `true`: Console shows DEBUG level (verbose output)
  - File logs always capture DEBUG regardless of this setting

### Fixed

- **`modify-task` now supports moving tasks to projects and areas** — new `project` and `area` parameters resolve names or UUIDs and use the Things URL scheme `list-id` parameter. Previously required raw URL scheme workarounds.
- **`update_todo()` now supports `list_id` parameter** — wires up the Things URL scheme `list-id` field for moving tasks between projects/areas
- **`format_todo()` now includes created date** — all task displays (process-inbox, get-tasks, search-tasks, etc.) now show when tasks were created
- **`process-inbox` decision tree references correct tool name** — changed `update-todo` to `modify-task` in the GTD decision tree guidance
- **convert-to-project now preserves checklist items and deadline**
  - Checklist items from the original task are converted to project tasks
  - Task deadline is preserved on the project (not on child tasks)
  - Only incomplete checklist items are converted (completed items are skipped)

### Documentation

- **n8n compatibility documentation** - New `docs/n8n-fastmcp-compatibility.md` documenting:
  - Extra parameter stripping (toolCallId, sessionId, etc.)
  - anyOf schema flattening for n8n's MCP client
  - Null value handling in tool arguments
  - Recommendations for FastMCP team

### Previous Changes

- **Upgraded to FastMCP 3.0.0b1** - Major framework upgrade with new features:
  - All tool functions converted to `async def` for better performance
  - Added `Context` dependency injection for operation logging via `await ctx.info()`
  - Implemented tool timeouts: write operations (30s), read operations (5s)
  - New error handling pattern: `raise ToolError("message")` instead of returning error strings
  - Fixed deprecation warning for `datetime.utcnow()` → `datetime.now(datetime.UTC)`

### Fixed

- Fixed 39 ruff linting errors including unused imports, bare except clauses, and duplicate function definitions
- Applied consistent code formatting across 18 files
- Updated async test suite to properly await tool function calls

## [2.0.0] - 2025-10-16

### BREAKING CHANGES

- **Removed legacy MCP implementation** - Consolidated to FastMCP-only implementation
  - Deleted `/things_server.py` - Legacy entry point
  - Deleted `/src/things_mcp/things_server.py` - Legacy MCP server
  - Deleted `/src/things_mcp/simple_server.py` - Simple server variant
  - Deleted `/src/things_mcp/simple_url_scheme.py` - Legacy URL scheme
  - Deleted `/src/things_mcp/mcp_tools.py` - Legacy tool registration

### Migration Guide

If upgrading from 1.x:

1. **Update MCP client configuration:**
   - Old: `"command": "things_server.py"`
   - New: `"command": "things_fast_server.py"`

2. **Update any scripts or automation:**
   - Old: `mcp dev things_server.py`
   - New: `mcp dev things_fast_server.py`

3. **No tool changes required** - All 19 MCP tools remain with identical signatures

### Benefits of 2.0

- ✅ **Simpler codebase** - Removed ~714 lines of duplicate code
- ✅ **Better reliability** - All users now get circuit breaker, caching, and retry logic automatically
- ✅ **Easier maintenance** - Single implementation to test and update
- ✅ **Clearer documentation** - No more confusion about which implementation to use

### Changed

- Updated project description to emphasize production-ready nature
- Bumped version to 2.0.0 across all configuration files
- Streamlined documentation with consolidated migration guide

## [1.0.0] - 2025-05-30

### Added

- 🚀 **FastMCP Implementation**: Complete rewrite using FastMCP pattern for better maintainability
- 🔄 **Reliability Features**:
  - Circuit breaker pattern to prevent cascading failures
  - Exponential backoff retry logic for transient failures
  - Dead letter queue for failed operations
- ⚡ **Performance Optimizations**:
  - Intelligent caching system with TTL management
  - Rate limiting to prevent overwhelming Things app
  - Automatic cache invalidation on data modifications
- 🍎 **AppleScript Bridge**: Fallback mechanism when URL schemes fail
- 📊 **Enhanced Monitoring**:
  - Structured JSON logging
  - Performance metrics and statistics
  - Comprehensive error tracking
  - Debug-friendly output
- 🛡️ **Error Handling**: Comprehensive exception management and recovery
- 🧪 **Test Suite**: Extensive tests for reliability
- 📦 **Smithery Support**: Full configuration for Smithery registry deployment
- 📝 **Documentation**: Enhanced README with detailed setup and troubleshooting guides

### Changed

- Rebranded to "Things 3 Enhanced MCP" for clear differentiation
- Updated package name to `mcp_things`
- Improved configuration token handling
- Enhanced URL scheme operations with better error recovery

### Fixed

- Token configuration import issues
- URL scheme reliability problems
- Various edge cases in task/project operations

### Attribution

Based on the original [things-mcp](https://github.com/hald/things-mcp) by Harald Lindstrøm

[1.0.0]: https://github.com/CaseyRo/mcp-things/releases/tag/v1.0.0
