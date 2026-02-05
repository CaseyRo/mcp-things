# Design: Deep MCP Integration Testing

## Context

The Things MCP server implements dual transport support (SSE for ChatGPT, streamable-http for n8n/Claude Desktop) but lacks comprehensive integration tests that verify protocol compliance and client compatibility through actual MCP protocol calls.

**Client Support Verification:**

- **n8n**: Supports **streamable-http transport only** (non-streamable HTTP) as of v1.102.3+ (MCP Client Tool node).
- **ChatGPT**: Should use **streamable-http transport** (modern standard). SSE is deprecated as of MCP protocol version 2025-03-26. OpenAI Agents SDK notes: "Prefer Streamable HTTP or stdio for new integrations".
- **SSE Support**: Will be removed after this work is complete. No SSE testing needed.

Current test coverage includes:

- Transport endpoint configuration (routes exist)
- Lifespan management (startup/shutdown)
- Accept header handling
- Configuration validation
- Basic CRUD operations (via direct tool function calls)

Missing test coverage:

- Actual MCP protocol requests/responses
- Transport-specific protocol requirements
- Client compatibility patches in real scenarios
- End-to-end workflows through protocol layer

## Goals

1. **Protocol Compliance**: Verify server correctly implements MCP specification for both transports
2. **Client Compatibility**: Verify n8n and ChatGPT compatibility patches work correctly
3. **CRUD Verification**: Verify complete workflows work through actual protocol calls
4. **Error Handling**: Verify error responses conform to MCP format
5. **Cross-Transport Consistency**: Verify same operations work identically via both transports

## Non-Goals

- Testing FastMCP framework itself (assumed to work correctly)
- Testing things-py library (assumed to work correctly)
- Performance/load testing (out of scope)
- Security testing (out of scope)

## Decisions

### Decision: Implement Custom MCP Test Client

**What**: Create a lightweight MCP protocol client in `tests/mcp_client.py` for making real protocol requests.

**Why**:

- Need to test actual protocol layer, not just tool functions
- Existing tests call tool functions directly, bypassing protocol
- Need to verify request/response format compliance
- Need to test transport-specific behavior

**Alternatives Considered**:

- Use existing MCP SDK client: Too heavy, may have its own bugs
- Mock protocol layer: Doesn't test real protocol compliance
- Use external tools (curl, httpx): Too low-level, hard to maintain

**Trade-offs**:

- Custom client requires maintenance but gives full control
- Can test exact protocol requirements without SDK abstractions

### Decision: Streamable-HTTP Transport Testing Only

**What**: Focus exclusively on streamable-http transport testing for both n8n and ChatGPT compatibility. Skip SSE testing entirely.

**Why**:

- **n8n**: Only supports streamable-http (non-streamable HTTP)
- **ChatGPT**: Should use streamable-http (modern standard), SSE is deprecated
- Streamable-http is the current MCP standard (as of protocol version 2025-03-26)
- SSE support will be removed after this work is complete
- Different client compatibility needs (n8n extra params vs ChatGPT strict schema) but same transport
- Single transport focus simplifies testing and maintenance

**Alternatives Considered**:

- Test SSE separately: SSE is deprecated and will be removed, unnecessary work
- Test both equally: SSE is legacy and being removed, waste of effort

**Trade-offs**:

- No SSE testing means we don't verify legacy endpoint (acceptable since it's being removed)
- Focus on streamable-http ensures modern standard compliance
- Cleaner test suite without deprecated transport tests

### Decision: Use Real Server Instances for Integration Tests

**What**: Start actual server instances for integration tests rather than mocking.

**Why**:

- Need to test actual HTTP/SSE communication
- Need to verify transport configuration works end-to-end
- Need to test lifespan management in real scenarios

**Alternatives Considered**:

- Mock ASGI app: Doesn't test real transport behavior
- Use test client (TestClient): Limited SSE support, doesn't test real HTTP

**Trade-offs**:

- Slower tests but more realistic
- May require Things 3 for full CRUD tests (can skip gracefully)

### Decision: Mark Tests with Appropriate Pytest Markers

**What**: Use `@pytest.mark.integration` for protocol tests, `@pytest.mark.real` for tests requiring Things 3.

**Why**:

- Allows selective test execution (unit vs integration)
- CI/CD can run fast unit tests, developers run full suite
- Tests requiring Things 3 can be skipped in CI

**Alternatives Considered**:

- All tests as unit tests: Misleading, some require server/Things 3
- All tests as integration: Slower, harder to run fast feedback loops

**Trade-offs**:

- Requires discipline to mark tests correctly
- Provides flexibility for different test execution scenarios

### Decision: Reuse Existing TestDataTracker for Auto-Cleanup

**What**: Use the existing `TestDataTracker` fixture from `tests/conftest.py` for automatic test data cleanup.

**Why**:

- Already implemented and tested in existing real integration tests
- Provides automatic cleanup via `test_data_tracker` fixture
- Includes session-scoped cleanup for leftover test data
- Uses `MCP-TEST-` prefix pattern for test data identification
- Avoids code duplication and maintains consistency

**Alternatives Considered**:

- Create new cleanup mechanism: Unnecessary duplication
- Manual cleanup: Error-prone, easy to forget

**Trade-offs**:

- Must use same test data prefix pattern (`MCP-TEST-*`)
- Relies on existing cleanup implementation (which is well-tested)

## Risks / Trade-offs

### Risk: Test Complexity

**Risk**: MCP protocol client implementation may become complex and hard to maintain.

**Mitigation**:

- Keep client implementation minimal (only what's needed for tests)
- Document protocol requirements clearly
- Consider extracting to shared test utility if reused

### Risk: Test Execution Time

**Risk**: Integration tests may be slow, blocking fast feedback.

**Mitigation**:

- Mark tests appropriately for selective execution
- Use fixtures to reuse server instances where possible
- Consider parallel test execution

### Risk: Things 3 Dependency

**Risk**: Full CRUD tests require Things 3, limiting CI/CD execution.

**Mitigation**:

- Mark tests requiring Things 3 with `@pytest.mark.real`
- Use existing `test_data_tracker` fixture for automatic cleanup (already excludes from pre-commit)
- Tests are automatically skipped in CI/CD via existing `skip_real_tests_if_unavailable` fixture
- Document test requirements clearly

### Risk: Protocol Specification Changes

**Risk**: MCP specification may evolve, requiring test updates.

**Mitigation**:

- Reference specific specification versions in tests
- Document protocol requirements clearly
- Keep tests aligned with FastMCP implementation

## Migration Plan

1. **Phase 1**: Implement MCP protocol test client
2. **Phase 2**: Add streamable-http integration tests
3. **Phase 3**: Add SSE integration tests
4. **Phase 4**: Add end-to-end CRUD tests
5. **Phase 5**: Add protocol compliance tests
6. **Phase 6**: Validate with real clients (n8n, ChatGPT)

No migration needed - these are new tests, not changes to existing functionality.

## Open Questions

1. Should we test request batching (multiple JSON-RPC requests in one HTTP request)? **Answer**: Out of scope for initial implementation, can add later if needed.
2. Should we test SSE reconnection scenarios? **Answer**: Out of scope for initial implementation, can add later if needed.
3. Should we test concurrent client connections? **Answer**: Out of scope for initial implementation, can add later if needed.
4. ~~How to handle test data cleanup for CRUD tests (auto-cleanup vs manual)?~~ **Answer**: Use existing `TestDataTracker` fixture from `conftest.py` - provides automatic cleanup with `test_data_tracker` fixture, uses `MCP-TEST-*` prefix pattern, already integrated with pre-commit exclusions.
