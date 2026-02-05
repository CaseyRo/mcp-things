# Change: Add Deep MCP Integration Tests

## Why

The Things MCP server currently has basic transport configuration tests but lacks comprehensive integration tests that verify:

1. **Streamable-HTTP Transport Compliance**: The server correctly implements the MCP streamable-http transport specification (modern standard for both n8n and ChatGPT)
2. **End-to-End CRUD Operations**: Complete Create-Read-Update-Delete workflows work correctly through actual MCP protocol calls
3. **Client-Specific Compatibility**: n8n and ChatGPT compatibility patches function correctly in real scenarios
4. **Protocol Compliance**: Requests and responses conform to MCP specification requirements

Without these tests, we cannot confidently verify that:

- Tool discovery (`list_tools`) works correctly via streamable-http transport
- Tool invocation (`call_tool`) handles parameters and returns proper responses
- Error handling conforms to MCP error response format
- Client-specific quirks (n8n extra params, ChatGPT schema requirements) are handled correctly
- CRUD operations complete successfully end-to-end through the protocol

Adding comprehensive integration tests improves confidence in production deployments, enables safe refactoring of protocol handling, and ensures compatibility with modern MCP clients.

## What Changes

- **MCP Protocol Test Client**: Create a test client that implements MCP protocol to make real requests to the server
- **Streamable-HTTP Integration Tests**: Create `tests/test_mcp_streamable_http.py` with tests for:
  - Tool discovery via `POST /mcp` with proper Accept headers
  - Tool invocation with various parameter combinations
  - Error handling and response format validation
  - n8n-specific compatibility (extra params, null values, anyOf flattening) - **n8n supports streamable-http as of v1.102.3+**
  - CRUD operations through streamable-http transport
- **End-to-End CRUD Tests**: Create `tests/test_mcp_crud_integration.py` with:
  - Complete workflows: create → read → update → delete
  - **Streamable-http transport focus**: Primary testing via streamable-http (modern standard for both n8n and ChatGPT)
  - Error recovery and retry scenarios
  - Data integrity verification
  - **Auto-cleanup**: Reuse existing `test_data_tracker` fixture from `conftest.py` (no new cleanup code needed)
- **Protocol Compliance Tests**: Create `tests/test_mcp_protocol.py` with:
  - JSON-RPC message format validation
  - Request/response structure validation
  - Error code and message format validation
  - Transport-specific protocol requirements

## Impact

- **Affected specs**: `mcp-integration-testing` (new capability)
- **Affected code**:
  - New test files: `tests/test_mcp_streamable_http.py`, `tests/test_mcp_crud_integration.py`, `tests/test_mcp_protocol.py`
  - New test utilities: MCP protocol client implementation for testing
  - May require test fixtures for running server instances
- **Development Workflow**:
  - Integration tests run as part of test suite (marked with `@pytest.mark.integration`)
  - Can be run separately from unit tests for faster iteration
  - Tests requiring Things 3 marked with `@pytest.mark.real` (auto-excluded from pre-commit)
  - Uses existing `test_data_tracker` fixture for automatic cleanup
- **Code Quality**: Ensures protocol compliance and client compatibility before deployment
- **Pre-deployment Validation**: Comprehensive verification that streamable-http transport works correctly with n8n and ChatGPT (modern standard)
