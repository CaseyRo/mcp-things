
# AGENTS

This file tracks the agent's thoughts, ideas, and work flow for the `mcp_things` repository.

## Instructions

- Append a new entry under `## Log` for each change made.
- Briefly describe the reasoning behind significant decisions.
- Run `ruff check .` and `pytest` after modifications.

## Log

### 2025-10-16 (continued)

- Implemented OpenSpec change `add-mcp-crud-tests` - Comprehensive test suite for MCP operations
  - Created `tests/` directory with full test infrastructure
  - Added `tests/conftest.py` with fixtures for both mocked unit tests and real Things 3 integration tests
  - Implemented unit tests (mocked) for all CRUD operations: todos, projects, read operations, integration workflows, error handling
  - Implemented real integration tests with automatic cleanup using `test_data_tracker` fixture
  - Added test commands to `pyproject.toml`: `test` (unit only, CI/CD safe), `test:dev` (all tests), `test:unit`, `test:integration`
  - Updated `pytest.ini` to exclude real integration tests by default (`-m "not real"`)
  - Added `pytest-asyncio` dependency for async test support
  - Created comprehensive `TESTING.md` documentation
  - Updated README.md with testing section
  - All tests use pytest markers: `unit` (default), `integration`, `real` (dev only), `slow`
  - Real integration tests gracefully skip if Things 3 is not available
  - Test coverage target: >80% on handler functions

### 2025-10-16 (continued)

- Implemented OpenSpec change `modernize-osascript-fastmcp` - Background execution for AppleScript operations
  - Modified `run_applescript()` in `applescript_bridge.py` to automatically wrap Things3 commands with `without activating` clause
  - Added `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable to allow disabling background execution for debugging
  - Updated `tag_handler.py` to use `run_applescript()` instead of direct subprocess calls for consistency
  - Updated `utils.py` to use `run_applescript()` for Things3 operations (version detection, app state checks)
  - Reviewed FastMCP integration - confirmed it already uses modern best practices (introspection for backward compatibility, metadata usage, proper annotations)
  - Updated README.md to document new environment variable in Configuration section
  - All AppleScript operations now run in background by default, preventing Things from appearing in foreground and interrupting user workflow

### 2025-10-16

- **Completed and archived OpenSpec change `remove-legacy-mcp` - Consolidated to FastMCP-only implementation (v2.0.0)**
  - Deleted 5 legacy files: things_server.py, simple_server.py, simple_url_scheme.py, mcp_tools.py, and src/things_mcp/things_server.py
  - Updated pyproject.toml, smithery.yaml, and **init**.py to version 2.0.0
  - Updated README.md: removed Migration & Deprecation section, added concise Version 2.0 Changes section
  - Created comprehensive CHANGELOG.md entry for 2.0.0 with breaking changes and migration guide
  - Maintained all 19 MCP tool APIs - full backward compatibility at tool level
  - Removed ~714 lines of duplicate code, simplified maintenance
  - Archived to openspec/changes/archive/2025-10-16-remove-legacy-mcp/
- Created OpenSpec change proposal `remove-legacy-mcp` for consolidating to FastMCP-only implementation
  - Comprehensive proposal.md documenting why (dual-implementation burden), what (remove 5 legacy files), and impact (breaking change → v2.0.0)
  - Detailed tasks.md with 8 implementation phases: pre-flight checks, code removal, import cleanup, config updates, documentation, testing, versioning, validation
  - Design.md with technical decisions, migration plan, risks/mitigations, rollback strategy
  - No spec deltas needed (implementation consolidation maintains all 19 tool APIs)
- Created comprehensive openspec/project.md with full project context (purpose, tech stack, conventions, domain knowledge, constraints, dependencies)
- Cleaned up and improved README.md based on openspec structure:
  - Enhanced overview and key benefits section
  - Added prerequisites section upfront
  - Better organized features by category (Things 3 Integration, Reliability, MCP)
  - Complete inventory of all 19 MCP tools with descriptions
  - Added architecture diagram and data flow
  - New sections: Usage with AI Assistants, Code Quality, Troubleshooting, Migration & Deprecation
  - Fixed all 44 markdown linting errors
- Removed redundant documentation files:
  - Deleted RELEASE_NOTES.md (redundant with CHANGELOG.md)
  - Deleted IMPLEMENTATION_SUMMARY.md (covered by openspec/project.md, README.md, and AGENTS.md)
- Updated smithery.yaml to align with improved documentation:
  - Refreshed descriptions to match new README
  - Added all 19 tools (was only 10)
  - Added THINGS_MCP_HOST and THINGS_MCP_PORT config options
  - Updated tags for better discoverability

### 2025-10-11

- Added shared MCP error helper returning `CallToolResult` and updated tool handlers to use it for failure cases.

### 2025-10-11

- Added MCP tool annotations across registration and Fast/Simple server implementations to align with MCP metadata expectations.

### 2025-10-11

- Added CLI flags and env var validation to the run script so operators can easily bind to alternate hosts and ports without manual exports.
- Extended FastMCP server binding logic and README guidance to document the new port override support.

### 2025-10-10

- Added FastMCP constructor introspection for icon support and guarded icon metadata so older runtimes still launch cleanly.

### 2025-10-09

- Added compatibility helper so FastMCP icon metadata works whether or not `mcp.types.Icon` is available in the runtime.
- Guarded FastMCP server construction so `website_url` metadata is only passed when supported by the installed MCP version.

### 2025-10-07

- Implemented logging redaction across handlers and the AppleScript bridge so user task content stays out of logs.
- Removed duplicate binding announcements from the CLI entrypoint so runtime logging only happens once and cached the binding helper for reuse.
- Clarified binding logs and helper exports so launchers surface localhost default without double logging.
- Switched FastMCP server default bind address to localhost with env override and documented exposure steps.
- Added FastMCP metadata (instructions, website, icon) constants and wired them into the server instantiation.
- Documented the surfaced assistant guidance in the README to mirror the MCP experience.
- Converted MCP icon metadata to use `mcp.types.Icon` objects to satisfy FastMCP validation.

### 2025-09-01

- Added `run_things_fastmcp.sh` helper script and integrated Rich logging.
- Documented macOS limitations preventing Docker usage for opening scripts.
- Introduced this AGENTS.md to record ongoing work.

### 2025-09-01

- Updated run script to bootstrap a uv-managed virtual environment or fall back to system Python.
- Clarified Quick Start docs about the helper script's environment handling.

### 2025-10-07

- Added standalone privacy and terms documents so operators understand local data handling and policy expectations.
- Updated README to link to the new policies and prompt users to review them before setup, keeping onboarding aligned with compliance guidance.
