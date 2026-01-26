# Design: ChatGPT MCP Compatibility

## Context

ChatGPT's MCP integration uses "strict mode" for function calling, which has stricter JSON Schema requirements than the base MCP specification:

1. `additionalProperties: false` on every object
2. All properties listed in `required` array
3. No `anyOf`/`oneOf`/`allOf` constructs (we already handle this for n8n)

## Decision: Single Transformation Pipeline

**What:** Apply all transformations (n8n + ChatGPT) to all requests.

**Why:** ChatGPT's requirements are a superset of n8n's. Applying the stricter transformations works for both clients:

| Transformation | n8n | ChatGPT | Breaks either? |
|----------------|-----|---------|----------------|
| Flatten `anyOf` | Needs | Needs | No |
| `additionalProperties: false` | Ignores | Needs | No |
| All fields in `required` | Ignores | Needs | No |
| Strip extra params | Needs | Ignores | No |

This avoids configuration complexity and "just works" for all clients.

## Schema Transformation Pipeline

### Order of Operations

```python
def transform_schema(schema: dict) -> dict:
    # Step 1: Flatten anyOf (existing - for n8n and ChatGPT)
    schema = _flatten_anyof_for_n8n(schema)

    # Step 2: Add additionalProperties: false (new - for ChatGPT)
    schema = _add_additional_properties_false(schema)

    # Step 3: Make all fields required (new - for ChatGPT)
    schema = _make_all_fields_required(schema)

    return schema
```

### Example Transformation

**Input (Pydantic-generated):**
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "notes": {"anyOf": [{"type": "string"}, {"type": "null"}]}
  },
  "required": ["title"]
}
```

**Output (ChatGPT-compatible):**
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

## Implementation Notes

### `_add_additional_properties_false()`

Recursively traverse the schema and add `additionalProperties: false` to any object that has `properties` defined.

### `_make_all_fields_required()`

1. Get all property names from `properties`
2. For properties not already in `required`, add `null` to their type
3. Set `required` to include all property names
4. Recurse into nested objects

## Risks

### Risk: Transformation breaks edge case schemas

**Mitigation:** Unit tests with various schema structures. Existing n8n tests serve as regression tests.
