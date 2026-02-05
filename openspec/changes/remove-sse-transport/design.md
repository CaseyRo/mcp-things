# Design: Remove SSE Transport Support

## Context

The Things MCP server currently implements dual transport support (SSE for ChatGPT, streamable-http for n8n/Claude Desktop). SSE transport is deprecated in the MCP protocol as of version 2025-03-26, and modern clients exclusively use streamable-http transport. Maintaining dual transport support adds unnecessary complexity and maintenance burden.

**Current State:**

- SSE transport endpoint at `/sse/` for ChatGPT compatibility
- Streamable-HTTP transport endpoint at `/mcp` for n8n/Claude Desktop
- Transport configuration supports "both", "sse", or "streamable-http"
- Default transport mode is "both" (enables both transports)
- Dual transport logic in `_create_combined_app()` function
- SSE-specific tests and fixtures

**Target State:**

- Single streamable-http transport endpoint at `/mcp`
- Transport configuration only supports "streamable-http"
- Default transport mode is "streamable-http"
- Simplified app creation logic (no dual transport handling)
- Streamable-HTTP-only tests with comprehensive CRUD coverage

## Goals

1. **Remove Legacy SSE Support**: Eliminate all SSE transport code, endpoints, and configuration
2. **Simplify Architecture**: Reduce code complexity by removing dual transport logic
3. **Standardize on Modern Protocol**: Align with MCP protocol standard (streamable-http only)
4. **Maintain Client Compatibility**: Ensure n8n and ChatGPT work correctly with streamable-http
5. **Comprehensive Testing**: Add thorough MCP protocol integration tests for streamable-http with CRUD operations

## Non-Goals

- Supporting backward compatibility with SSE clients (explicitly removing support)
- Adding new transport protocols
- Performance optimization (out of scope)
- Security enhancements (out of scope)

## Decisions

### Decision: Remove SSE Transport Completely

**What**: Remove all SSE transport code, endpoints, tests, and configuration options.

**Why**:

- SSE is deprecated in MCP protocol (2025-03-26)
- Modern clients (n8n, ChatGPT) use streamable-http exclusively
- Reduces code complexity and maintenance burden
- Eliminates need for dual transport testing

**Alternatives Considered**:

- Keep SSE as deprecated/legacy option: Adds maintenance burden for deprecated feature
- Gradual deprecation: SSE is already deprecated in protocol, no need for gradual removal
- Feature flag: Adds complexity without benefit since SSE is protocol-deprecated

**Trade-offs**:

- Breaking change for any users still using SSE endpoint (unlikely given protocol deprecation)
- Simpler codebase and reduced maintenance burden
- Aligns with modern MCP protocol standard

### Decision: Simplify Transport Configuration to Single Option

**What**: Change transport configuration from `Literal["both", "sse", "streamable-http"]` to `Literal["streamable-http"]` with default "streamable-http".

**Why**:

- Only one transport option remains, no need for selection
- Simplifies configuration and validation
- Removes ambiguity about which transport to use

**Alternatives Considered**:

- Keep "both" option pointing to streamable-http: Confusing, implies multiple transports
- Keep transport setting but only allow "streamable-http": More explicit but adds unnecessary validation

**Trade-offs**:

- Breaking change for users with `THINGS_MCP_TRANSPORT="both"` or `THINGS_MCP_TRANSPORT="sse"`
- Simpler configuration (can remove transport setting entirely, but keeping it allows future extensibility)
- Clearer intent: only one transport supported

## Risks / Trade-offs

### Risk: Breaking Changes for Existing Users

**Risk**: Users with `THINGS_MCP_TRANSPORT="both"` or `THINGS_MCP_TRANSPORT="sse"` will need to update configuration.

**Mitigation**:

- Clear migration documentation in CHANGELOG.md
- Update default to "streamable-http" (most users likely use default)
- Document breaking change prominently

### Risk: Missing Edge Cases in SSE Removal

**Risk**: May miss SSE-specific code paths that cause errors after removal.

**Mitigation**:

- Comprehensive code review of all SSE references
- Run full test suite after changes
- Verify server starts and responds correctly

### Risk: Client Compatibility Issues

**Risk**: ChatGPT or n8n may have issues with streamable-http-only configuration.

**Mitigation**:

- Verify n8n compatibility (already uses streamable-http)
- ChatGPT should use streamable-http per OpenAI Agents SDK guidance
- Test with actual clients if possible

### Risk: Test Coverage Gaps

**Risk**: Removing SSE tests may leave gaps in streamable-http test coverage.

**Mitigation**:

- Add comprehensive streamable-http CRUD tests
- Verify all critical operations tested via protocol layer
- Review existing test coverage before removal

## Migration Plan

1. **Phase 1**: Remove SSE transport code from `fast_server.py`
2. **Phase 2**: Simplify transport configuration in `settings.py`
3. **Phase 3**: Remove SSE tests and update remaining tests
4. **Phase 4**: Add comprehensive streamable-http CRUD tests
5. **Phase 5**: Update documentation and Node-RED flow
6. **Phase 6**: Validate with tests and real clients
7. **Phase 7**: Update CHANGELOG.md with breaking changes

**Rollback Strategy**: If issues arise, can revert commits, but SSE support should not be restored as it's protocol-deprecated.

### Decision: Update Node-RED Flow to Remove SSE Endpoints

**What**: Update docs/node-red-flow.json to remove all SSE endpoint handlers (GET, POST, DELETE `/things/sse`) while keeping the streamable-http endpoint (`POST /things/mcp`).

**Why**:

- SSE endpoints are no longer available on server
- Node-RED flow should match server capabilities
- Keeps the flow useful for users who want to proxy MCP requests
- Prevents confusion about which endpoints to use

**Alternatives Considered**:

- Remove docs/node-red-flow.json entirely: Users may find it useful for proxying requests
- Keep SSE endpoints pointing to streamable-http: Confusing, incorrect endpoint names
- Leave SSE endpoints as-is: Will fail when server doesn't have SSE endpoint

**Trade-offs**:

- Breaking change for Node-RED users using SSE endpoints (but SSE is deprecated anyway)
- Cleaner flow that matches server capabilities
- Forces users to use correct streamable-http endpoint

## Open Questions

1. Should we remove the transport configuration setting entirely (since only one option exists)? **Answer**: Keep it for future extensibility, but simplify to single option.
2. Are there any SSE-specific dependencies that need removal? **Answer**: Verified `pyproject.toml` - `wsproto` is for WebSocket protocol (not SSE), no SSE-specific dependencies found. No dependency changes needed.
3. Should we add migration warnings for users with old transport settings? **Answer**: Validation error is sufficient - clear error message guides users.
