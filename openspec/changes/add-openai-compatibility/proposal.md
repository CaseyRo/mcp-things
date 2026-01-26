# Change: Add OpenAI/ChatGPT MCP Compatibility

## Why

OpenAI's MCP integration (ChatGPT) has stricter JSON Schema requirements than the MCP specification. When connecting Things MCP to ChatGPT, tool schemas are rejected with validation errors because OpenAI requires `strict` mode compliance that standard MCP schemas don't provide.

This is a known issue affecting all MCP servers trying to integrate with OpenAI - see [FastMCP #855](https://github.com/jlowin/fastmcp/issues/855) and [github-mcp-server #376](https://github.com/github/github-mcp-server/issues/376).

## What Changes

- **Extend schema transformation pipeline** - Add OpenAI strict mode transformations alongside existing n8n fixes
- **Single code path** - Apply all transformations for all clients (OpenAI requirements are a superset of n8n)
- **Documentation** - Document ChatGPT compatibility patterns (like we did for n8n)

### OpenAI Strict Mode Requirements (in addition to n8n)

1. **`additionalProperties: false`** - Must be set on every object in the schema
2. **All fields in `required`** - Every property must be listed in `required` array

We already handle:
- `anyOf` flattening (works for both n8n and OpenAI)
- Null value stripping in middleware (harmless for OpenAI)

### Why One Path Works for Both

| Transformation | n8n needs? | OpenAI needs? | Apply to all? |
|----------------|------------|---------------|---------------|
| Flatten `anyOf` | Yes | Yes | Yes |
| `additionalProperties: false` | No (but harmless) | Yes | Yes |
| All fields in `required` | No (but harmless) | Yes | Yes |
| Strip extra params | Yes | No (but harmless) | Yes |

## Impact

- Affected specs: `client-compatibility` (new capability)
- Affected code: `src/things_mcp/server_core.py` - Schema transformation functions
- No configuration needed - works automatically for both n8n and ChatGPT
- No breaking changes

## References

- [FastMCP Issue #855](https://github.com/jlowin/fastmcp/issues/855)
- [github-mcp-server Issue #376](https://github.com/github/github-mcp-server/issues/376)
