# Client Compatibility Specification

## ADDED Requirements

### Requirement: ChatGPT Strict Mode Schema Compatibility

The system SHALL transform tool schemas to comply with ChatGPT's strict mode requirements.

ChatGPT strict mode requires:
1. `additionalProperties: false` on all object schemas
2. All properties listed in the `required` array
3. No `anyOf`, `oneOf`, or `allOf` constructs (already handled for n8n)

#### Scenario: additionalProperties added to object schemas

- **WHEN** a ListToolsRequest is received
- **THEN** tool schemas SHALL include `additionalProperties: false` on all object types
- **AND** nested objects SHALL also have `additionalProperties: false`

#### Scenario: All fields made required with nullable types

- **GIVEN** a tool with an optional parameter `notes` of type `Optional[str]`
- **WHEN** the schema is transformed
- **THEN** the parameter SHALL have type `["string", "null"]`
- **AND** the parameter SHALL be listed in `required`

#### Scenario: Required fields remain non-nullable

- **GIVEN** a tool with a required parameter `title` of type `str`
- **WHEN** the schema is transformed
- **THEN** the parameter SHALL have type `string` (not an array)
- **AND** the parameter SHALL be listed in `required`

### Requirement: Unified Client Compatibility

The system SHALL apply all schema transformations for all MCP clients without requiring configuration.

Transformations applied:
1. Flatten `anyOf` to type arrays (n8n + ChatGPT)
2. Add `additionalProperties: false` to objects (ChatGPT)
3. Make all fields required with nullable types (ChatGPT)
4. Strip n8n-specific parameters from tool calls (n8n)

#### Scenario: n8n client works with ChatGPT transformations

- **GIVEN** transformations are applied for ChatGPT compatibility
- **WHEN** an n8n client connects
- **THEN** tools SHALL be listed successfully
- **AND** tool calls SHALL execute successfully

#### Scenario: ChatGPT client works with n8n middleware

- **GIVEN** n8n middleware strips extra parameters
- **WHEN** a ChatGPT client connects (without extra parameters)
- **THEN** tools SHALL be listed successfully
- **AND** tool calls SHALL execute successfully

### Requirement: Backward Compatibility with n8n

The system SHALL maintain backward compatibility with n8n MCP Client Tool.

#### Scenario: n8n extra parameters still stripped

- **WHEN** a tool call includes n8n-specific parameters (`toolCallId`, `sessionId`, `action`, `chatInput`)
- **THEN** these parameters SHALL be stripped before validation

#### Scenario: n8n null values still handled

- **WHEN** a tool call includes explicit null values for optional parameters
- **THEN** these null values SHALL be stripped before validation
