# n8n + FastMCP Compatibility Guide

This document describes the compatibility issues between n8n's MCP Client Tool and FastMCP servers, along with the workarounds implemented in this project. The code samples are simplified; the real implementation is `ClientCompatibilityMiddleware` in `src/things_mcp/server_core.py`.

## Background

n8n (v1.70+) includes an MCP Client Tool that can connect to Model Context Protocol servers. However, there are several compatibility issues when using it with FastMCP servers.

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

**Applying it:** `ClientCompatibilityMiddleware.on_list_tools` runs the flattener over every tool's input and output schema before `tools/list` is returned. No request handler is patched.

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

## Complete Implementation

See `src/things_mcp/server_core.py` for the complete implementation including:

- `ClientCompatibilityMiddleware` class (`on_list_tools` schema transforms, `on_call_tool` parameter and null stripping)
- `_flatten_anyof_for_n8n()` function

## Testing n8n Compatibility

1. Enable debug logging:

   ```bash
   export THINGS_MCP_DEBUG=true
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

## See Also

- `docs/chatgpt-fastmcp-compatibility.md` - ChatGPT-specific compatibility (additionalProperties, required fields)
