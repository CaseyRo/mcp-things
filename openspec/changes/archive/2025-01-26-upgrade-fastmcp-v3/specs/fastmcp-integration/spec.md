# Spec: FastMCP Integration

## Overview

Things MCP uses the FastMCP framework for MCP server implementation.

## Requirements

### REQ-1: FastMCP v3 Dependency

- The project MUST depend on `fastmcp>=3.0.0`
- The project MUST NOT depend on `mcp[cli]`

### REQ-2: Import Structure

- FastMCP class MUST be imported from `fastmcp`
- ToolAnnotations MUST be imported from `fastmcp.server.types` or `mcp.types`
- Middleware MUST be imported from `fastmcp.server.middleware`

### REQ-3: Tool Registration

- All tools MUST use the `@mcp.tool()` decorator
- All tools MUST have a `timeout` parameter set
- All tools MUST have appropriate `annotations`

### REQ-4: Error Handling

- Tool errors MUST raise `ToolError` from `fastmcp.exceptions`
- Tool errors MUST NOT return emoji-prefixed strings

### REQ-5: Context Integration

- Async tools MAY accept a `ctx: Context` parameter
- Context parameter MUST be optional for backwards compatibility
- Context logging SHOULD use `await ctx.info()` for user-visible status

### REQ-6: Timeout Configuration

- Read-only tools: 5 seconds
- Write operations: 30 seconds
- UI operations: 10 seconds

## Non-Requirements

- ToolResult structured responses are not required (string returns are acceptable)
- Context parameter is optional, not mandatory
