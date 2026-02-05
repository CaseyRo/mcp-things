## MODIFIED Requirements

### Requirement: FastMCP Server Configuration

The system SHALL use modern FastMCP patterns and best practices for server configuration, tool registration, and error handling.

The system SHALL review and adopt FastMCP features that improve reliability, performance, or maintainability when available in the minimum supported version (mcp[cli]>=1.2.0).

The system SHALL use introspection to detect available FastMCP constructor parameters and gracefully handle older runtime versions that may not support newer metadata fields.

#### Scenario: FastMCP metadata introspection

- **WHEN** the FastMCP server is initialized
- **THEN** the system checks available constructor parameters via `inspect.signature()`
- **AND** newer metadata fields (website_url, icons) are only included if supported
- **AND** older runtimes without these features continue to work

#### Scenario: Tool registration consistency

- **WHEN** tools are registered with FastMCP
- **THEN** all tools use appropriate annotations (readOnlyHint, idempotentHint, destructiveHint)
- **AND** tool descriptions are clear and helpful for AI assistants

## ADDED Requirements

### Requirement: FastMCP Best Practices Review

The system SHALL periodically review FastMCP integration to ensure adherence to current best practices and leverage new features when beneficial.

#### Scenario: FastMCP feature review

- **WHEN** the FastMCP integration is reviewed
- **THEN** the system checks for async/await patterns that could improve performance
- **AND** the system evaluates declarative configuration options (fastmcp.json) if available
- **AND** improvements are documented and implemented if they provide clear value

#### Scenario: Async handler evaluation

- **WHEN** tool handlers are reviewed for async capabilities
- **THEN** handlers are evaluated for potential async improvements (e.g., parallel operations, non-blocking I/O)
- **AND** async is adopted only when it provides clear performance or reliability benefits
