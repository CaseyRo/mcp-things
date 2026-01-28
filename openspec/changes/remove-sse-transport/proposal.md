# Change: Remove SSE Transport Support

## Why

SSE (Server-Sent Events) transport is deprecated in the MCP protocol as of version 2025-03-26. Modern clients (n8n v1.102.3+, ChatGPT via OpenAI Agents SDK) use streamable-http transport exclusively. Maintaining dual transport support adds unnecessary complexity, increases maintenance burden, and requires testing multiple code paths for deprecated functionality.

**Client Support Verification:**
- **n8n**: Supports streamable-http transport only (non-streamable HTTP) as of v1.102.3+ (MCP Client Tool node)
- **ChatGPT**: Should use streamable-http transport (modern standard). SSE is deprecated as of MCP protocol version 2025-03-26. OpenAI Agents SDK notes: "Prefer Streamable HTTP or stdio for new integrations"
- **SSE Support**: No longer needed - removing legacy support simplifies the codebase

## What Changes

- **BREAKING**: Remove SSE transport endpoint (`/sse/`) and all SSE-related code
- **BREAKING**: Simplify transport configuration - remove "both" and "sse" options, keep only "streamable-http"
- **BREAKING**: Update default transport mode from "both" to "streamable-http"
- Remove SSE-related tests and test fixtures
- Verify no SSE-specific dependencies exist (confirmed: `wsproto` is for WebSocket, not SSE)
- Update node-red-flow.json to remove SSE endpoints, keep only streamable-http endpoint
- Update documentation to remove SSE references and add transport configuration details
- Simplify `_create_combined_app()` function - no longer needs dual transport logic

## Impact

- **Affected specs**: `server-testing` (remove SSE requirements, add streamable-http CRUD testing)
- **Affected code**: 
  - `src/things_mcp/fast_server.py` - Remove SSE transport creation logic
  - `src/things_mcp/settings.py` - Simplify transport enum to only "streamable-http"
  - `src/things_mcp/client_compat.py` - Remove SSE-related compatibility code (if any)
  - `tests/test_transport_endpoints.py` - Remove SSE tests
  - `tests/test_transport_smoke.py` - Remove SSE tests
  - `tests/test_lifespan.py` - Remove SSE lifespan tests
  - `tests/test_server_startup.py` - Remove SSE endpoint tests
  - `tests/test_configuration.py` - Update transport validation tests
  - `tests/test_accept_headers.py` - May simplify (SSE-specific headers)
  - `docs/node-red-flow.json` - Remove SSE endpoint handlers, keep streamable-http endpoint
  - Documentation files (README.md, docs/CLAUDE.md, docs/DEVELOPERS.md) - Remove SSE references, add transport config docs
- **Migration**: Users must update `THINGS_MCP_TRANSPORT` environment variable from "both" or "sse" to "streamable-http" (or remove it to use default)
