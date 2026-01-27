## ADDED Requirements

### Requirement: MCP Protocol Test Client
The system SHALL provide a test client implementation that can make real MCP protocol requests to verify server compliance.

#### Scenario: Streamable-HTTP client implementation
- **WHEN** a test needs to make streamable-http requests
- **THEN** the test client can send POST requests with JSON-RPC messages to `/mcp` endpoint

#### Scenario: SSE client implementation
- **WHEN** a test needs to make SSE requests
- **THEN** the test client can establish SSE connections and parse event streams from `/sse/` endpoint

#### Scenario: Tool discovery helper
- **WHEN** a test needs to discover available tools
- **THEN** the test client provides a helper method that sends `list_tools` request and parses response

#### Scenario: Tool invocation helper
- **WHEN** a test needs to invoke a tool
- **THEN** the test client provides a helper method that sends `call_tool` request with parameters and parses response

### Requirement: Streamable-HTTP Integration Tests
The system SHALL provide integration tests that verify streamable-http transport compliance and n8n compatibility.

#### Scenario: Tool discovery via streamable-http
- **WHEN** a `list_tools` request is sent via POST to `/mcp` endpoint
- **THEN** the test verifies the response contains valid tool definitions with correct schema format

#### Scenario: Tool invocation with required parameters
- **WHEN** a `call_tool` request is sent with only required parameters
- **THEN** the test verifies the tool executes successfully and returns proper response format

#### Scenario: Tool invocation with optional parameters
- **WHEN** a `call_tool` request is sent with optional parameters included
- **THEN** the test verifies the tool executes successfully with all parameters applied

#### Scenario: Error handling for invalid tool name
- **WHEN** a `call_tool` request is sent with invalid tool name
- **THEN** the test verifies the server returns MCP-compliant error response

#### Scenario: Error handling for invalid parameters
- **WHEN** a `call_tool` request is sent with invalid parameter types or values
- **THEN** the test verifies the server returns MCP-compliant error response

#### Scenario: n8n extra parameters stripped
- **WHEN** a `call_tool` request includes n8n-specific extra parameters (toolCallId, sessionId, action, chatInput)
- **THEN** the test verifies these parameters are stripped before validation and tool executes successfully

#### Scenario: n8n null values handled
- **WHEN** a `call_tool` request includes explicit null values for optional parameters
- **THEN** the test verifies null values are stripped and tool executes successfully

#### Scenario: n8n anyOf schema flattening
- **WHEN** tool schemas are retrieved via `list_tools` through streamable-http
- **THEN** the test verifies anyOf constructs are flattened to type arrays for n8n compatibility (n8n uses streamable-http only)

#### Scenario: ChatGPT compatibility via streamable-http
- **WHEN** tool schemas are retrieved via `list_tools` through streamable-http
- **THEN** the test verifies all object schemas have `additionalProperties: false` for ChatGPT compatibility (ChatGPT should use streamable-http, modern standard)

#### Scenario: ChatGPT required fields via streamable-http
- **WHEN** tool schemas are retrieved via `list_tools` through streamable-http
- **THEN** the test verifies all properties are listed in `required` array with nullable types for optional fields (ChatGPT strict mode requirements)

#### Scenario: Accept header wildcard support
- **WHEN** a request is sent with wildcard Accept header (`*/*`)
- **THEN** the test verifies the request is accepted and processed correctly

#### Scenario: CRUD create via streamable-http
- **WHEN** a todo is created via `call_tool` with `add-todo` through streamable-http transport
- **THEN** the test verifies the todo is created successfully and response indicates success

#### Scenario: CRUD read via streamable-http
- **WHEN** todos are retrieved via `call_tool` with `get-todos` through streamable-http transport
- **THEN** the test verifies todos are returned in correct format

#### Scenario: CRUD update via streamable-http
- **WHEN** a todo is updated via `call_tool` with `update-todo` through streamable-http transport
- **THEN** the test verifies the todo is updated successfully

#### Scenario: CRUD delete via streamable-http
- **WHEN** a todo is canceled/deleted via `call_tool` with `update-todo` (canceled=true) through streamable-http transport
- **THEN** the test verifies the todo is canceled successfully


### Requirement: End-to-End CRUD Integration Tests
The system SHALL provide tests that verify complete CRUD workflows work correctly through MCP protocol.

#### Scenario: Complete CRUD workflow via streamable-http
- **WHEN** a complete workflow is executed (create todo → read todos → update todo → cancel todo) via streamable-http
- **THEN** the test verifies each step succeeds and data integrity is maintained

#### Scenario: n8n CRUD workflow via streamable-http
- **WHEN** a complete workflow is executed (create todo → read todos → update todo → cancel todo) via streamable-http with n8n compatibility
- **THEN** the test verifies each step succeeds and data integrity is maintained

#### Scenario: ChatGPT CRUD workflow via streamable-http
- **WHEN** a complete workflow is executed (create todo → read todos → update todo → cancel todo) via streamable-http with ChatGPT schema requirements
- **THEN** the test verifies each step succeeds and data integrity is maintained

#### Scenario: Project CRUD workflow
- **WHEN** a complete project workflow is executed (create project → add todos → read project → update project → delete project)
- **THEN** the test verifies each step succeeds and project data integrity is maintained

#### Scenario: Error recovery
- **WHEN** an invalid operation is attempted, then retried with correct parameters
- **THEN** the test verifies error is handled correctly and retry succeeds

#### Scenario: Data integrity verification
- **WHEN** a todo is created with specific parameters
- **THEN** the test verifies reading the todo returns matching data

### Requirement: Protocol Compliance Tests
The system SHALL provide tests that verify MCP protocol compliance for requests and responses.

#### Scenario: JSON-RPC request format
- **WHEN** a request is sent to the server
- **THEN** the test verifies the request conforms to JSON-RPC 2.0 format

#### Scenario: JSON-RPC response format
- **WHEN** a response is received from the server
- **THEN** the test verifies the response conforms to JSON-RPC 2.0 format

#### Scenario: MCP error response format
- **WHEN** an error occurs during tool execution
- **THEN** the test verifies the error response includes required fields (code, message) in MCP format

#### Scenario: Tool schema format compliance
- **WHEN** tool schemas are retrieved via `list_tools`
- **THEN** the test verifies schemas conform to JSON Schema format and MCP requirements

#### Scenario: Streamable-http transport requirements
- **WHEN** requests are made via streamable-http transport
- **THEN** the test verifies requests use POST method and include proper Accept headers

#### Scenario: SSE transport requirements
- **WHEN** requests are made via SSE transport
- **THEN** the test verifies event stream format conforms to SSE specification
