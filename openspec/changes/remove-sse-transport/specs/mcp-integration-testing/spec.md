## MODIFIED Requirements

### Requirement: Streamable-HTTP CRUD Integration Tests

The system SHALL provide comprehensive integration tests that verify CRUD operations work correctly via streamable-http transport using actual MCP protocol calls. These tests already exist in `test_mcp_crud_integration.py` and `test_mcp_streamable_http.py`.

#### Scenario: Complete CRUD workflow via streamable-http transport

- **WHEN** existing tests in `test_mcp_crud_integration.py` perform a complete CRUD workflow (create, read, update, delete) via streamable-http transport
- **THEN** the tests verify all operations succeed and data consistency is maintained

#### Scenario: n8n compatibility CRUD workflow

- **WHEN** existing tests simulate n8n MCP Client Tool node requests with extra parameters via streamable-http transport
- **THEN** the tests verify extra parameters are handled correctly and CRUD operations succeed

#### Scenario: ChatGPT compatibility CRUD workflow

- **WHEN** existing tests make MCP protocol requests via streamable-http transport with strict schema validation
- **THEN** the tests verify requests are processed correctly and responses conform to strict schema requirements
