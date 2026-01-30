# Changelog

All notable changes to Things 3 Enhanced MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### BREAKING CHANGES

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
  - New `tools_deprecated.py` - Backward-compatible aliases (18 tools)
  - Each module now has focused responsibility, easier to test and maintain

### Added

- **THINGS_MCP_DEBUG environment variable** - Enable verbose console logging for debugging
  - When `false` (default): Console shows INFO level only
  - When `true`: Console shows DEBUG level (verbose output)
  - File logs always capture DEBUG regardless of this setting

### Fixed

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
- Updated package name to `things3-enhanced-mcp`
- Improved configuration token handling
- Enhanced URL scheme operations with better error recovery

### Fixed
- Token configuration import issues
- URL scheme reliability problems
- Various edge cases in task/project operations

### Attribution
Based on the original [things-mcp](https://github.com/hald/things-mcp) by Harald Lindstrøm

[1.0.0]: https://github.com/CaseyRo/things-fastmcp/releases/tag/v1.0.0
