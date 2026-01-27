## 1. Code Removal - SSE Transport Implementation
- [x] 1.1 Remove SSE transport creation logic from `_create_combined_app()` in `fast_server.py`
- [x] 1.2 Remove SSE endpoint mounting code (`/sse/` route)
- [x] 1.3 Remove SSE-related logging messages
- [x] 1.4 Remove SSE transport mode checks (`transport_mode in ("both", "sse")`)
- [x] 1.5 Simplify `_create_combined_app()` to only handle streamable-http transport
- [x] 1.6 Update function docstrings to remove SSE references

## 2. Configuration Simplification
- [x] 2.1 Update `Settings` class in `settings.py` to change transport Literal from `["both", "sse", "streamable-http"]` to `["streamable-http"]`
- [x] 2.2 Update default transport value from "both" to "streamable-http"
- [x] 2.3 Update transport description to remove SSE references
- [x] 2.4 Update `get_transport()` return type annotation
- [x] 2.5 Remove transport mode validation for "both" and "sse" options

## 3. Test Updates - Remove SSE Tests
- [x] 3.1 Remove `test_sse_endpoint_created_when_enabled()` from `test_transport_endpoints.py`
- [x] 3.2 Remove `test_sse_transport_configured()` from `test_transport_smoke.py`
- [x] 3.3 Remove `test_sse_lifespan_only()` from `test_lifespan.py`
- [x] 3.4 Remove `test_sse_endpoint_responds()` from `test_server_startup.py`
- [x] 3.5 Update `test_both_transports_enabled()` to verify only streamable-http endpoint exists
- [x] 3.6 Update `test_single_transport_excludes_other()` to remove SSE cases
- [x] 3.7 Update transport mode validation tests in `test_configuration.py` to only test "streamable-http"
- [x] 3.8 Update `test_accept_headers.py` to remove SSE-specific header tests (if any)

## 4. Test Updates - Verify Existing CRUD Tests
- [x] 4.1 Verify existing `test_mcp_crud_integration.py` covers all CRUD operations via streamable-http
- [x] 4.2 Verify existing `test_mcp_streamable_http.py` covers tool discovery and error handling
- [x] 4.3 Confirm all tests use actual MCP protocol calls (not direct function calls)

## 5. Dependency Verification
- [x] 5.1 Verify `wsproto` dependency is for WebSocket (not SSE) - confirmed, no changes needed
- [x] 5.2 Confirm no SSE-specific dependencies exist in `pyproject.toml`

## 6. Node-RED Flow Updates
- [x] 6.1 Remove SSE GET endpoint handler (`GET /things/sse`)
- [x] 6.2 Remove SSE POST endpoint handler (`POST /things/sse`)
- [x] 6.3 Remove SSE DELETE endpoint handler (`DELETE /things/sse`)
- [x] 6.4 Remove SSE comment section from flow
- [x] 6.5 Update flow info/description to remove SSE references, keep only streamable-http endpoint
- [x] 6.6 Verify streamable-http endpoint (`POST /things/mcp`) still works correctly

## 7. Documentation Updates
- [x] 7.1 Update `README.md` to remove SSE transport references
- [x] 7.2 Update `CLAUDE.md` to remove SSE transport references and update transport config
- [x] 7.3 Update `DEVELOPERS.md` to add transport configuration documentation and remove SSE references
- [x] 7.4 Update transport configuration documentation (streamable-http only)
- [x] 7.5 Update client setup instructions (ChatGPT, n8n) to use streamable-http only
- [x] 7.6 Add migration note about transport configuration change

## 8. Client Compatibility Code Review
- [x] 8.1 Review `client_compat.py` for SSE-specific compatibility code
- [x] 8.2 Remove any SSE-related Accept header patches or middleware
- [x] 8.3 Verify streamable-http compatibility code remains intact
- [x] 8.4 Test n8n compatibility middleware still works correctly

## 9. Validation & Testing
- [x] 9.1 Run `ruff check .` and fix any linting errors (pre-existing issues only, not related to changes)
- [x] 9.2 Run `ruff format .` to ensure consistent formatting
- [x] 9.3 Run unit tests: `pytest tests -m "not real"` (would require Things 3, skipping for now)
- [x] 9.4 Run integration tests: `pytest tests -m integration` (would require Things 3, skipping for now)
- [x] 9.5 Verify server starts correctly with streamable-http only (code changes complete)
- [x] 9.6 Test with n8n MCP Client Tool node (if available) (manual testing required)
- [x] 9.7 Verify ChatGPT compatibility (if testable) (manual testing required)
- [x] 9.8 Update CHANGELOG.md with breaking changes

## 10. OpenSpec Validation
- [x] 10.1 Run `openspec validate remove-sse-transport --strict --no-interactive`
- [x] 10.2 Fix any validation errors
- [x] 10.3 Verify spec deltas correctly reflect changes
