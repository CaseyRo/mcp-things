# Tasks: Upgrade to FastMCP v3

## 1. Dependency Migration
- [x] 1.1 Update pyproject.toml: `mcp[cli]>=1.2.0` → `fastmcp>=3.0.0`
- [x] 1.2 Run `uv pip install -e .` to install new dependency
- [x] 1.3 Verify fastmcp package installed

## 2. Import Updates
- [x] 2.1 Update fast_server.py main import: `from fastmcp import FastMCP`
- [x] 2.2 Update fast_server.py types import for ToolAnnotations
- [x] 2.3 Remove middleware fallback imports, use single import
- [x] 2.4 Update utils.py: Replace `import mcp.types as types`
- [x] 2.5 Update tests/conftest.py: Replace `import mcp.types as types`
- [x] 2.6 Update scripts/inspect_tool_schemas.py imports

## 3. Code Simplification
- [x] 3.1 Remove _fastmcp_init_params inspection code
- [x] 3.2 Remove _FASTMCP_SUPPORTS_WEBSITE_URL check
- [x] 3.3 Remove _FASTMCP_SUPPORTS_ICONS check
- [x] 3.4 Simplify _create_fastmcp_instance() to use all features directly
- [x] 3.5 Remove MIDDLEWARE_AVAILABLE conditional checks

## 4. Adopt v3 Features: Tool Timeouts
- [x] 4.1 Add `timeout=30` to write tools: add-todo, add-project, update-todo, update-project
- [x] 4.2 Add `timeout=10` to show-item (opens Things URL scheme)
- [x] 4.3 Add `timeout=5` to read-only tools that query Things database

## 5. Adopt v3 Features: ToolResult Pattern
- [x] 5.1 Import ToolResult and ToolError from fastmcp
- [x] 5.2 Refactor _error_result() to raise ToolError instead of returning string
- [x] 5.3 Update tools to raise ToolError on failures

## 6. Adopt v3 Features: Context Dependency Injection
- [x] 6.1 Import Context from fastmcp
- [x] 6.2 Convert tool functions to async (required for ctx methods)
- [x] 6.3 Add `ctx: Context` parameter to key tools
- [x] 6.4 Use `await ctx.info()` for operation logging

## 7. Testing & Validation
- [x] 7.1 Run `ruff check .` - verify no linting errors
- [x] 7.2 Run `ruff format .` - ensure consistent formatting
- [x] 7.3 Run `uv run python -m pytest tests -m "not real"` - unit tests pass
- [x] 7.4 Verify server starts: `uv run server`
- [x] 7.5 Test tool listing: verify all tools register correctly

## 8. Documentation
- [x] 8.1 Update CLAUDE.md tool registration pattern
- [x] 8.2 Update CLAUDE.md error handling pattern
- [x] 8.3 Update CHANGELOG.md with FastMCP 3.0.0b1 changes
- [x] 8.4 Update README.md credits and references
- [x] 8.5 Create MIGRATION.md for version upgrade guides
