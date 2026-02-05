## MODIFIED Requirements

### Requirement: Transport Endpoint Configuration Tests

The system SHALL provide tests that verify streamable-http transport endpoint is correctly configured.

#### Scenario: Streamable-HTTP endpoint created when enabled

- **WHEN** transport mode is set to "streamable-http"
- **THEN** the test verifies the `/mcp` endpoint is created and mounted correctly

#### Scenario: Single transport endpoint exists

- **WHEN** transport mode is set to "streamable-http"
- **THEN** the test verifies only `/mcp` endpoint exists (no `/sse` endpoint)

### Requirement: Lifespan Management Tests

The system SHALL provide tests that verify lifespan events are properly handled for streamable-http transport setup.

#### Scenario: Lifespan startup completes

- **WHEN** an app with streamable-http transport is created
- **THEN** the test verifies lifespan startup completes without errors

#### Scenario: Lifespan shutdown graceful

- **WHEN** an app with streamable-http transport completes its lifespan
- **THEN** the test verifies shutdown completes gracefully without errors

#### Scenario: Streamable-HTTP transport lifespan

- **WHEN** streamable-http transport is configured
- **THEN** the test verifies its lifespan works correctly

### Requirement: Configuration Validation Tests

The system SHALL provide tests that verify settings are correctly loaded and validated.

#### Scenario: Default settings are valid

- **WHEN** settings are loaded without environment overrides
- **THEN** the test verifies default values are correct (host=127.0.0.1, port=8009, transport=streamable-http)

#### Scenario: Transport mode validation

- **WHEN** transport mode is set to "streamable-http"
- **THEN** the test verifies the mode is accepted

- **WHEN** transport mode is set to invalid values ("both", "sse", or other)
- **THEN** the test verifies ValidationError is raised

### Requirement: Server Startup Smoke Tests

The system SHALL provide smoke tests that verify the server can start and endpoints respond correctly.

#### Scenario: Server starts successfully

- **WHEN** the server process is started
- **THEN** the test verifies the process runs without immediate errors

#### Scenario: Streamable-HTTP endpoint responds

- **WHEN** the server is running and streamable-http endpoint is enabled
- **THEN** the test verifies HTTP requests to `/mcp` receive a response (200, 404, or 405)

#### Scenario: Graceful handling when server unavailable

- **WHEN** smoke tests are run but server is not accessible
- **THEN** the test gracefully skips without failing the test suite

### Requirement: Transport Smoke Tests

The system SHALL provide fast smoke tests that verify transport configuration without starting a full server, suitable for pre-commit hooks.

#### Scenario: Streamable-HTTP transport configured

- **WHEN** transport mode is set to "streamable-http"
- **THEN** the test verifies only `/mcp` endpoint exists and app structure is valid

#### Scenario: App has lifespan configured

- **WHEN** an app is created with streamable-http transport mode
- **THEN** the test verifies the app has lifespan configuration for proper startup/shutdown

#### Scenario: Streamable-HTTP transport creates valid app

- **WHEN** transport mode "streamable-http" is used to create an app
- **THEN** the test verifies a valid app is created with routes configured

## REMOVED Requirements

### Requirement: SSE Transport Endpoint Configuration

**Reason**: SSE transport is deprecated in MCP protocol (2025-03-26) and removed from server implementation.
**Migration**: Use streamable-http transport endpoint at `/mcp` instead.

### Requirement: Dual Transport Configuration

**Reason**: Only streamable-http transport is supported. No need for dual transport logic.
**Migration**: Set `THINGS_MCP_TRANSPORT=streamable-http` (or use default).

### Requirement: SSE Transport Lifespan Tests

**Reason**: SSE transport removed, no SSE-specific lifespan tests needed.
**Migration**: Use streamable-http transport lifespan tests instead.
