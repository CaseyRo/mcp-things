# n8n + FastMCP 3.0 Compatibility Guide

This document describes the compatibility issues between n8n's MCP Client Tool and FastMCP 3.0 servers, along with the workarounds implemented in this project.

## Background

n8n (v1.70+) includes an MCP Client Tool that can connect to Model Context Protocol servers. However, there are several compatibility issues when using it with FastMCP 3.0 servers.

## Issue 1: Extra Parameters in Tool Calls

**GitHub Issue:** [n8n-io/n8n#21500](https://github.com/n8n-io/n8n/issues/21500)

**Problem:** n8n's MCP Client Tool sends extra parameters with every tool call that aren't part of the tool's schema:
- `toolCallId`
- `sessionId`
- `action`
- `chatInput`

These cause Pydantic validation errors in FastMCP because they aren't declared in the tool's input schema.

**Error:**
```
Extra inputs are not permitted [type=extra_forbidden, input_value='call_abc123', input_type=str]
```

**Solution:** Implement middleware that strips these parameters before validation.

```python
from fastmcp.server.middleware import Middleware

N8N_EXTRA_PARAMS = {"toolCallId", "sessionId", "action", "chatInput"}

class N8NCompatibilityMiddleware(Middleware):
    """Strip extra parameters that n8n's MCP Client Tool sends."""

    async def on_call_tool(self, context, call_next):
        if hasattr(context, "message") and hasattr(context.message, "arguments"):
            args = context.message.arguments
            if args:
                # Remove n8n-specific parameters
                for param in list(N8N_EXTRA_PARAMS):
                    if param in args:
                        del args[param]
        return await call_next(context)

# Add to server
mcp.add_middleware(N8NCompatibilityMiddleware())
```

## Issue 2: `anyOf` Schema Constructs

**Problem:** n8n's MCP client doesn't handle `anyOf` constructs in JSON Schema properly. Pydantic generates these for `Optional[T]` types:

```json
{
  "anyOf": [
    {"type": "string"},
    {"type": "null"}
  ]
}
```

This causes n8n to throw:
```
Cannot read properties of undefined (reading 'inputType')
```

**Solution:** Patch the `ListToolsRequest` handler to flatten `anyOf` into JSON Schema type arrays:

```python
def _flatten_anyof_for_n8n(schema: dict) -> dict:
    """Transform anyOf into type arrays for n8n compatibility.

    Transforms:
      {"anyOf": [{"type": "string"}, {"type": "null"}]}
    Into:
      {"type": ["string", "null"]}
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        if key == "anyOf" and isinstance(value, list):
            has_null = any(t.get("type") == "null" for t in value)
            non_null_types = [t for t in value if t.get("type") != "null"]

            if len(non_null_types) == 1:
                flattened = _flatten_anyof_for_n8n(non_null_types[0])
                result.update(flattened)
                if has_null and "type" in result:
                    current_type = result["type"]
                    if isinstance(current_type, str):
                        result["type"] = [current_type, "null"]
                    elif isinstance(current_type, list) and "null" not in current_type:
                        result["type"] = current_type + ["null"]
            # ... handle multiple types
        elif key == "properties" and isinstance(value, dict):
            result[key] = {k: _flatten_anyof_for_n8n(v) for k, v in value.items()}
        elif isinstance(value, dict):
            result[key] = _flatten_anyof_for_n8n(value)
        elif isinstance(value, list):
            result[key] = [
                _flatten_anyof_for_n8n(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result
```

**Patching the Handler:**

```python
import mcp.types as mcp_types

def _patch_tool_serialization_for_n8n(mcp: FastMCP):
    """Patch ListToolsRequest to flatten anyOf for n8n."""
    request_handlers = mcp._mcp_server.request_handlers
    original_handler = request_handlers[mcp_types.ListToolsRequest]

    async def patched_list_tools_handler(request):
        result = await original_handler(request)
        tools = result.root.tools

        for tool in tools:
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                flattened = _flatten_anyof_for_n8n(tool.inputSchema)
                if isinstance(tool.inputSchema, dict):
                    tool.inputSchema.clear()
                    tool.inputSchema.update(flattened)

        return result

    request_handlers[mcp_types.ListToolsRequest] = patched_list_tools_handler
```

## Issue 3: Explicit Null Values

**Problem:** n8n sends explicit `null` values for empty optional fields. After flattening `anyOf` to type arrays, the schema no longer declares null as valid, causing validation errors.

**Solution:** Strip null values from arguments in the middleware:

```python
class N8NCompatibilityMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        if hasattr(context, "message") and hasattr(context.message, "arguments"):
            args = context.message.arguments
            if args:
                # Strip n8n params
                for param in list(N8N_EXTRA_PARAMS):
                    if param in args:
                        del args[param]

                # Strip null values
                null_params = [k for k, v in args.items() if v is None]
                for param in null_params:
                    del args[param]

        return await call_next(context)
```

Also patch the `CallToolRequest` handler for defense in depth:

```python
def _patch_tool_serialization_for_n8n(mcp: FastMCP):
    # ... ListToolsRequest patch ...

    # Patch CallToolRequest
    original_call_tool = request_handlers[mcp_types.CallToolRequest]

    async def patched_call_tool_handler(request):
        if request.params and request.params.arguments:
            args = request.params.arguments
            null_keys = [k for k, v in args.items() if v is None]
            for key in null_keys:
                del args[key]
        return await original_call_tool(request)

    request_handlers[mcp_types.CallToolRequest] = patched_call_tool_handler
```

## Complete Implementation

See `src/things_mcp/server_core.py` for the complete implementation including:
- `N8NCompatibilityMiddleware` class
- `_flatten_anyof_for_n8n()` function
- `_patch_tool_serialization_for_n8n()` function

## Testing n8n Compatibility

1. Enable debug logging:
   ```bash
   export THINGS_MCP_DEBUG_SCHEMA=1
   ```

2. Start the server and check logs for schema transformations

3. Connect n8n's MCP Client Tool and verify tools are listed

4. Test tool execution with optional parameters

## Recommendations for FastMCP Team

1. **Consider built-in n8n compatibility mode** - Many users will want to use FastMCP with n8n

2. **Schema format option** - Allow servers to specify schema format preferences (anyOf vs type arrays)

3. **Middleware documentation** - Document the middleware API for request/response modification

4. **Input sanitization hooks** - Provide hooks for stripping unknown parameters before validation

## References

- [n8n MCP Client Tool Issue #21500](https://github.com/n8n-io/n8n/issues/21500)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [JSON Schema Type Arrays](https://json-schema.org/understanding-json-schema/reference/type.html)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
