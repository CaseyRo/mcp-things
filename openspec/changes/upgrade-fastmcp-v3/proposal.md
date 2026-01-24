# Change: Upgrade to FastMCP v3

## Why

FastMCP v3.0.0 is the new standalone package replacing the `mcp[cli]` package. It offers:
- Cleaner import paths (flat structure)
- Guaranteed feature availability (no version detection needed)
- New features: tool timeouts, Context dependency injection, ToolResult pattern
- Simplified middleware API
- Better compatibility with n8n and other MCP clients

## What Changes

- **Dependency**: Replace `mcp[cli]>=1.2.0` with `fastmcp>=3.0.0`
- **Imports**: Update all import paths from `mcp.server.fastmcp` to `fastmcp`
- **Version Detection**: Remove runtime feature detection code
- **Middleware**: Simplify to single import path
- **Tool Timeouts**: Add timeout parameter to all tools
- **ToolResult Pattern**: Use structured responses instead of plain strings
- **Context DI**: Add context parameter for logging and progress reporting

## Impact

- Affected specs: `fastmcp-integration`
- Affected code:
  - `pyproject.toml` - Dependency declaration
  - `src/things_mcp/fast_server.py` - Core server implementation
  - `src/things_mcp/utils.py` - Type imports
  - `tests/conftest.py` - Test fixtures
  - `scripts/inspect_tool_schemas.py` - Diagnostic tooling
