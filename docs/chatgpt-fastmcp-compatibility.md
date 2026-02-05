# ChatGPT + FastMCP 3.0 Compatibility Guide

This document describes the compatibility issues between ChatGPT's MCP integration and FastMCP 3.0 servers, along with the solutions implemented in this project.

## Background

ChatGPT adopted MCP in March 2025. However, ChatGPT uses "strict mode" for function calling, which has stricter JSON Schema requirements than the base MCP specification.

## Issue 1: Missing `additionalProperties: false`

**GitHub Issues:**

- [github-mcp-server #376](https://github.com/github/github-mcp-server/issues/376)
- [FastMCP #855](https://github.com/jlowin/fastmcp/issues/855)

**Problem:** ChatGPT strict mode requires `additionalProperties: false` on every object in the schema. Standard MCP schemas (and Pydantic-generated schemas) don't include this.

**Error:**

```
Invalid schema for function 'add_issue_comment': In context=(), 'additionalProperties' is required to be supplied and to be false.
```

**Solution:** Recursively add `additionalProperties: false` to all object schemas.

```python
def _add_additional_properties_false(schema: dict) -> dict:
    """Recursively add additionalProperties: false to all objects."""
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    # If this is an object with properties, add additionalProperties: false
    if result.get("type") == "object" or "properties" in result:
        if "additionalProperties" not in result:
            result["additionalProperties"] = False

    # Recurse into properties
    if "properties" in result:
        result["properties"] = {
            k: _add_additional_properties_false(v)
            for k, v in result["properties"].items()
        }

    # Recurse into items (for arrays)
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _add_additional_properties_false(result["items"])

    return result
```

## Issue 2: Optional Fields Must Be in `required` Array

**Problem:** ChatGPT strict mode requires ALL properties to be listed in the `required` array. Optional fields should use type arrays like `["string", "null"]` instead of being omitted from `required`.

**ChatGPT Documentation:**
> "If you turn on `strict: true` in the function calling schema, then you have to list all of your fields under `required`."

**Before (Standard JSON Schema):**

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "notes": {"type": "string"}
  },
  "required": ["title"]
}
```

**After (ChatGPT Strict Mode):**

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "notes": {"type": ["string", "null"]}
  },
  "required": ["title", "notes"],
  "additionalProperties": false
}
```

**Solution:** Add all properties to `required` and use type arrays for optional fields.

```python
def _make_all_fields_required(schema: dict) -> dict:
    """Add all properties to required array, using type arrays for optional fields."""
    if not isinstance(schema, dict):
        return schema

    result = dict(schema)

    if "properties" in result:
        all_props = list(result["properties"].keys())
        current_required = set(result.get("required", []))

        # For fields not currently required, make them nullable
        new_properties = {}
        for prop_name, prop_schema in result["properties"].items():
            prop_schema = _make_all_fields_required(prop_schema)  # Recurse first

            if prop_name not in current_required:
                # Add null to type for optional fields
                prop_schema = dict(prop_schema)
                if "type" in prop_schema:
                    current_type = prop_schema["type"]
                    if isinstance(current_type, str) and current_type != "null":
                        prop_schema["type"] = [current_type, "null"]
                    elif isinstance(current_type, list) and "null" not in current_type:
                        prop_schema["type"] = current_type + ["null"]

            new_properties[prop_name] = prop_schema

        result["properties"] = new_properties
        result["required"] = all_props

    # Recurse into items
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _make_all_fields_required(result["items"])

    return result
```

## Issue 3: `anyOf` Not Supported

**Problem:** ChatGPT strict mode doesn't support `anyOf`, `oneOf`, or `allOf` constructs. Pydantic generates `anyOf` for `Optional[T]` types.

**Error:**

```
Invalid schema: anyOf is not supported in strict mode
```

**Solution:** Flatten `anyOf` constructs to JSON Schema type arrays. This is the same solution we use for n8n compatibility - see `docs/n8n-fastmcp-compatibility.md`.

## Complete Transformation Pipeline

We apply all transformations to all requests (ChatGPT requirements are a superset of n8n):

```python
def _transform_schema_for_clients(schema: dict) -> dict:
    """Apply all client compatibility transformations."""
    # Step 1: Flatten anyOf (needed for both n8n and ChatGPT)
    schema = _flatten_anyof_for_n8n(schema)

    # Step 2: Add additionalProperties: false (ChatGPT)
    schema = _add_additional_properties_false(schema)

    # Step 3: Make all fields required (ChatGPT)
    schema = _make_all_fields_required(schema)

    return schema
```

## Why This Works for Both n8n and ChatGPT

| Transformation | n8n needs? | ChatGPT needs? | Breaks either? |
|----------------|------------|----------------|----------------|
| Flatten `anyOf` | Yes | Yes | No |
| `additionalProperties: false` | No | Yes | No (n8n ignores) |
| All fields in `required` | No | Yes | No (n8n ignores) |
| Strip extra params | Yes | No | No (ChatGPT doesn't send them) |

## Testing ChatGPT Compatibility

1. **Enable debug logging:**

   ```bash
   export THINGS_MCP_DEBUG_SCHEMA=1
   ```

2. **Use ngrok for HTTPS** (ChatGPT requires HTTPS):

   ```bash
   ngrok http 127.0.0.1:8009
   ```

3. **Connect ChatGPT to the ngrok HTTPS URL**

4. **Verify tools are listed and callable**

## Recommendations for FastMCP Team

### 1. Built-in Schema Transformations

Consider adding built-in schema transformation for common clients:

```python
server = FastMCP(
    "MyServer",
    schema_compat="strict"  # Applies ChatGPT-compatible transformations
)
```

### 2. Pydantic Model Configuration

Consider Pydantic configuration that generates strict-mode-compatible schemas:

```python
class ToolInput(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"additionalProperties": False}
    )
```

### 3. Documentation

Document the differences between MCP spec schemas and what various clients actually require.

## References

- [FastMCP Issue #855 - OpenAI Responses API](https://github.com/jlowin/fastmcp/issues/855)
- [github-mcp-server Issue #376 - additionalProperties](https://github.com/github/github-mcp-server/issues/376)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI Community: Schema additionalProperties](https://community.openai.com/t/schema-additionalproperties-must-be-false-when-strict-is-true/929996)

## See Also

- `docs/n8n-fastmcp-compatibility.md` - n8n-specific compatibility (anyOf flattening, parameter stripping)
