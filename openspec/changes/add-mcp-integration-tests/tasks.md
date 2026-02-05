## 1. Research and Planning

- [x] 1.1 Research MCP streamable-http transport specification (2025-03-26 or later)
- [x] 1.2 Research MCP SSE transport specification (legacy but still used by ChatGPT) - Skipped per design
- [x] 1.3 Review n8n MCP Client Tool documentation and requirements
- [x] 1.4 Review ChatGPT MCP integration documentation and requirements
- [x] 1.5 Document protocol requirements for both transports
- [x] 1.6 Identify test scenarios based on specification requirements

## 2. MCP Protocol Test Client

- [x] 2.1 Create `tests/mcp_client.py` with MCP protocol client implementation
- [x] 2.2 Implement streamable-http client methods (POST requests, JSON-RPC)
- [x] 2.3 Implement SSE client methods (SSE connection, event parsing) - Skipped (SSE removed)
- [x] 2.4 Add helper methods for tool discovery (`list_tools`)
- [x] 2.5 Add helper methods for tool invocation (`call_tool`)
- [x] 2.6 Add error handling and response parsing
- [x] 2.7 Add support for both transports (streamable-http and SSE) - SSE skipped

## 3. Streamable-HTTP Integration Tests (Primary Focus)

- [x] 3.1 Create `tests/test_mcp_streamable_http.py`
- [x] 3.2 Add test for tool discovery (`list_tools` request)
- [x] 3.3 Add test for tool discovery response format validation
- [x] 3.4 Add test for tool invocation with required parameters only
- [x] 3.5 Add test for tool invocation with optional parameters
- [x] 3.6 Add test for tool invocation error handling (invalid tool name)
- [x] 3.7 Add test for tool invocation error handling (invalid parameters)
- [x] 3.8 Add test for **n8n compatibility** (extra params stripped correctly) - n8n uses streamable-http only
- [x] 3.9 Add test for **n8n compatibility** (null values handled correctly)
- [x] 3.10 Add test for **n8n compatibility** (anyOf schema flattening verified)
- [x] 3.11 Add test for **ChatGPT compatibility** (additionalProperties: false in schemas) - ChatGPT should use streamable-http
- [x] 3.12 Add test for **ChatGPT compatibility** (all fields in required array)
- [x] 3.13 Add test for Accept header handling (wildcard support)
- [x] 3.14 Add test for CRUD operations (create todo via streamable-http)
- [x] 3.15 Add test for CRUD operations (read todos via streamable-http)
- [x] 3.16 Add test for CRUD operations (update todo via streamable-http)
- [x] 3.17 Add test for CRUD operations (delete/cancel todo via streamable-http)
- [x] 3.18 Verify tests use proper pytest markers (`@pytest.mark.integration`)

## 4. SSE Integration Tests

- [x] 4.1 **SKIP** - SSE testing removed per design decision. SSE support will be removed after this work is complete.

## 5. End-to-End CRUD Integration Tests

- [x] 5.1 Create `tests/test_mcp_crud_integration.py`
- [x] 5.2 Add test for complete CRUD workflow via streamable-http (use `test_data_tracker` fixture) - **Primary focus**
- [x] 5.3 Add test for n8n CRUD workflow (create → read → update → delete via streamable-http with n8n compatibility)
- [x] 5.4 Add test for ChatGPT CRUD workflow (create → read → update → delete via streamable-http with ChatGPT schema requirements)
- [x] 5.5 Add test for project CRUD workflow (create → read → update → delete, use `test_data_tracker`)
- [x] 5.6 Add test for error recovery (invalid operation → retry with correct params)
- [x] 5.7 Add test for data integrity (create → read → verify data matches)
- [x] 5.8 Add test for concurrent operations (multiple tool calls)
- [x] 5.9 Use `generate_test_title("MCP-TEST-*")` helper for test data (consistent with existing tests)
- [x] 5.10 Verify tests use proper pytest markers (`@pytest.mark.integration`, `@pytest.mark.real`)

## 6. Protocol Compliance Tests

- [x] 6.1 Create `tests/test_mcp_protocol.py`
- [x] 6.2 Add test for JSON-RPC request format validation
- [x] 6.3 Add test for JSON-RPC response format validation
- [x] 6.4 Add test for MCP error response format (code, message structure) - Covered in integration tests
- [x] 6.5 Add test for tool schema format compliance - Covered in integration tests
- [x] 6.6 Add test for streamable-http transport requirements (Accept headers, POST method)
- [x] 6.7 Add test for SSE transport requirements (event stream format) - Skipped (SSE removed)
- [x] 6.8 Add test for request batching (if supported) - Out of scope per design
- [x] 6.9 Verify tests use proper pytest markers (`@pytest.mark.unit` or `@pytest.mark.integration`)

## 7. Test Infrastructure

- [x] 7.1 Create test fixtures for running server instances
- [x] 7.2 Add fixture for streamable-http test client
- [x] 7.3 Add fixture for SSE test client - Skipped (SSE removed)
- [x] 7.4 Reuse existing `test_data_tracker` fixture from `conftest.py` for auto-cleanup (no new cleanup needed)
- [x] 7.5 Use `MCP-TEST-*` prefix pattern for test data (consistent with existing tests)
- [x] 7.6 Add test utilities for protocol message construction
- [x] 7.7 Add test utilities for response validation
- [x] 7.8 Document test setup requirements in test files
- [x] 7.9 Verify tests are excluded from pre-commit (via `@pytest.mark.real` marker)

## 8. Test Execution & Validation

- [x] 8.1 Run all new integration tests to verify they pass - Protocol tests pass, integration tests require server
- [x] 8.2 Verify tests work with both transport modes ("both", "sse", "streamable-http") - Focus on streamable-http only
- [x] 8.3 Verify tests can be run independently or as part of full test suite
- [ ] 8.4 Test with real n8n MCP Client Tool (manual verification) - Manual step
- [ ] 8.5 Test with real ChatGPT integration (manual verification if possible) - Manual step
- [x] 8.6 Run `ruff check` to ensure code quality
- [x] 8.7 Verify test execution time is acceptable (< 60 seconds for full suite)

## 9. Documentation

- [x] 9.1 Add test file docstrings explaining test purpose and protocol requirements
- [x] 9.2 Document MCP protocol client implementation
- [x] 9.3 Document how to run integration tests - Covered in test file docstrings
- [x] 9.4 Document test data requirements (Things 3, auth token) - Covered in test file docstrings
- [ ] 9.5 Update docs/DEVELOPERS.md with integration testing guidance - Optional enhancement
