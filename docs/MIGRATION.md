# Migration Guide

This guide covers upgrading from previous versions of Things 3 Enhanced MCP.

## Migrating from 1.x to 2.0

**Breaking Change:** Version 2.0 removed the legacy MCP implementation and consolidated to FastMCP-only.

### Update MCP Client Configuration

**Old configuration:**

```json
{
  "mcpServers": {
    "things": {
      "command": "things_server.py"
    }
  }
}
```

**New configuration:**

```json
{
  "mcpServers": {
    "things": {
      "command": "uv run server"
    }
  }
}
```

### Update Scripts and Automation

| Old | New |
|-----|-----|
| `mcp dev things_server.py` | `mcp dev things_fast_server.py` |
| `python things_server.py` | `uv run server` |

### What's Unchanged

- All 19 MCP tools remain with identical signatures
- Tool names and parameters are backward compatible
- No changes needed to your AI assistant prompts

### Benefits of 2.0

- Simpler codebase (~714 lines of duplicate code removed)
- Automatic reliability features (circuit breaker, caching, retry logic)
- Easier maintenance with single implementation
- Clearer documentation

## Migrating from Bash Script

If you were previously using the bash script (`./run_things_fastmcp.sh`):

**Old way:**

```bash
./run_things_fastmcp.sh
./run_things_fastmcp.sh --host 0.0.0.0 --port 9000
```

**New way:**

```bash
uv run server
THINGS_FASTMCP_HOST=0.0.0.0 THINGS_FASTMCP_PORT=9000 uv run server
```

**Benefits:**

- Simpler command syntax
- Better dependency management with UV
- Configuration via `.env` files
- No bash script maintenance overhead

## FastMCP 3.0 (Current)

The project now uses FastMCP 3.0.0b1. Key changes for developers:

- Tool functions are now `async def`
- Context dependency injection via `ctx: Context` parameter
- Error handling uses `raise ToolError("message")`
- Tool timeouts: write operations (30s), read operations (5s)

See [CHANGELOG.md](CHANGELOG.md) for full details.
