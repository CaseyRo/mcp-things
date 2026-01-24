# Design: FastMCP v3 Migration

## Architecture Changes

### Import Structure (Before → After)

```python
# Before
from mcp.server.fastmcp import FastMCP
import mcp.types as types

# After
from fastmcp import FastMCP
from fastmcp.server.types import ToolAnnotations
```

### Tool Pattern (Before → After)

```python
# Before - Sync, string returns, manual logging
@mcp.tool(name="add-todo", annotations=TOOL_ANNOTATIONS["add-todo"])
def add_task(title: str, notes: Optional[str] = None) -> str:
    log_operation_start("add-todo")
    try:
        # ... implementation
        return f"Successfully created todo: {title}"
    except Exception as e:
        return _error_result(f"Error creating todo: {str(e)}")

# After - Async, ToolError for errors, Context DI
@mcp.tool(name="add-todo", annotations=TOOL_ANNOTATIONS["add-todo"], timeout=30)
async def add_task(
    title: str,
    notes: Optional[str] = None,
    ctx: Context = None
) -> str:
    if ctx:
        await ctx.info("Creating todo...")
    try:
        # ... implementation
        if ctx:
            await ctx.info("Todo created successfully")
        return f"Successfully created todo: {title}"
    except Exception as e:
        raise ToolError(f"Error creating todo: {str(e)}")
```

### Error Handling Pattern

```python
# Before
def _error_result(message: str) -> str:
    return f"⚠️ {message}"

# After
from fastmcp.exceptions import ToolError

def _error_result(message: str):
    """Raise a ToolError for standardized MCP error handling."""
    raise ToolError(message)
```

## Feature Mapping

| v2 Feature | v3 Equivalent |
|------------|---------------|
| `mcp.server.fastmcp.FastMCP` | `fastmcp.FastMCP` |
| `mcp.types.ToolAnnotations` | `fastmcp.server.types.ToolAnnotations` |
| Version detection for features | All features available |
| Multiple middleware import attempts | Single `fastmcp.server.middleware.Middleware` |
| String error returns | `ToolError` exceptions |
| Manual operation logging | `ctx.info()`, `ctx.report_progress()` |

## Timeout Strategy

| Tool Category | Timeout | Rationale |
|--------------|---------|-----------|
| Read-only (get-*, search-*) | 5s | SQLite queries are fast |
| Write operations (add-*, update-*) | 30s | URL scheme + AppleScript execution |
| UI operations (show-item) | 10s | Opens Things window |

## Backwards Compatibility

- MCP clients continue receiving same tool schemas
- n8n compatibility middleware unchanged
- Tool names and parameters unchanged
- Return format unchanged (string responses)
