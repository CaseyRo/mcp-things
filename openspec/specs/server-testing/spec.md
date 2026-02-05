# server-testing Specification

## Purpose

Comprehensive test suite for verifying MCP server transport configuration, lifespan management, client compatibility, configuration validation, and server startup. Tests are organized into fast unit tests suitable for pre-commit hooks and slower integration tests for full server verification.

## Requirements

### Requirement: Transport Endpoint Configuration Tests

The system SHALL provide tests that verify SSE and streamable-http transport endpoints are correctly configured based on transport mode settings.

#### Scenario: SSE endpoint created when enabled

- **WHEN** transport mode is set to "sse" or "both"
- **THEN** the test verifies the `/sse` endpoint is created and mounted correctly

#### Scenario: Streamable-HTTP endpoint created when enabled

- **WHEN** transport mode is set to "streamable-http" or "both"
- **THEN** the test verifies the `/mcp` endpoint is created and mounted correctly

#### Scenario: Both transports enabled

- **WHEN** transport mode is set to "both"
- **THEN** the test verifies both `/sse` and `/mcp` endpoints exist

#### Scenario: Single transport excludes other

- **WHEN** transport mode is set to "sse" only
- **THEN** the test verifies `/mcp` endpoint does not exist

- **WHEN** transport mode is set to "streamable-http" only
- **THEN** the test verifies `/sse` endpoint does not exist

### Requirement: Lifespan Management Tests

The system SHALL provide tests that verify lifespan events are properly handled for dual transport setup.

#### Scenario: Lifespan startup completes

- **WHEN** a combined app with dual transports is created
- **THEN** the test verifies lifespan startup completes without errors for both transports

#### Scenario: Lifespan shutdown graceful

- **WHEN** a combined app with dual transports completes its lifespan
- **THEN** the test verifies shutdown completes gracefully without errors

#### Scenario: Independent transport lifespans

- **WHEN** SSE transport is configured independently
- **THEN** the test verifies its lifespan works correctly

- **WHEN** streamable-http transport is configured independently
- **THEN** the test verifies its lifespan works correctly

### Requirement: Accept Header Compatibility Tests

The system SHALL provide tests that verify Accept header patching and middleware function correctly for client compatibility.

#### Scenario: Accept header patch applies successfully

- **WHEN** the Accept header patch function is called
- **THEN** the test verifies the patch applies without errors

#### Scenario: Middleware rewrites wildcard headers

- **WHEN** a request is made with wildcard Accept header (`*/*`)
- **THEN** the test verifies middleware rewrites it to explicit types (`application/json, text/event-stream`)

#### Scenario: Middleware adds missing Accept header

- **WHEN** a request is made without an Accept header
- **THEN** the test verifies middleware adds the required Accept header

#### Scenario: Middleware preserves explicit valid headers

- **WHEN** a request is made with explicit valid Accept header (`application/json, text/event-stream`)
- **THEN** the test verifies middleware preserves the header unchanged

### Requirement: Configuration Validation Tests

The system SHALL provide tests that verify settings are correctly loaded and validated.

#### Scenario: Default settings are valid

- **WHEN** settings are loaded without environment overrides
- **THEN** the test verifies default values are correct (host=127.0.0.1, port=8009, transport=both)

#### Scenario: Transport mode validation

- **WHEN** transport mode is set to valid values ("both", "sse", "streamable-http")
- **THEN** the test verifies all valid modes are accepted

#### Scenario: Port validation

- **WHEN** port is set to valid values (1-65535)
- **THEN** the test verifies valid ports are accepted

- **WHEN** port is set to invalid values (< 1 or > 65535)
- **THEN** the test verifies ValidationError is raised

#### Scenario: Host validation

- **WHEN** host is set to valid IP addresses or hostnames
- **THEN** the test verifies valid hosts are accepted

#### Scenario: Auth token property

- **WHEN** auth token is set to a non-empty string
- **THEN** the test verifies `has_auth_token` property returns True

- **WHEN** auth token is set to empty string
- **THEN** the test verifies `has_auth_token` property returns False

#### Scenario: Retry configuration validation

- **WHEN** retry attempts is set to valid range (1-10)
- **THEN** the test verifies valid values are accepted

- **WHEN** retry attempts is set outside valid range
- **THEN** the test verifies ValidationError is raised

- **WHEN** retry delay is set to valid range (0.1-30.0)
- **THEN** the test verifies valid values are accepted

- **WHEN** retry delay is set outside valid range
- **THEN** the test verifies ValidationError is raised

### Requirement: Server Startup Smoke Tests

The system SHALL provide smoke tests that verify the server can start and endpoints respond correctly.

#### Scenario: Server starts successfully

- **WHEN** the server process is started
- **THEN** the test verifies the process runs without immediate errors

#### Scenario: SSE endpoint responds

- **WHEN** the server is running and SSE endpoint is enabled
- **THEN** the test verifies HTTP requests to `/sse/` receive a response (200, 404, or 405)

#### Scenario: Streamable-HTTP endpoint responds

- **WHEN** the server is running and streamable-http endpoint is enabled
- **THEN** the test verifies HTTP requests to `/mcp` receive a response (200, 404, or 405)

#### Scenario: Graceful handling when server unavailable

- **WHEN** smoke tests are run but server is not accessible
- **THEN** the test gracefully skips without failing the test suite

### Requirement: Transport Smoke Tests

The system SHALL provide fast smoke tests that verify transport configuration without starting a full server, suitable for pre-commit hooks.

#### Scenario: Both transports configured

- **WHEN** transport mode is set to "both"
- **THEN** the test verifies both `/sse` and `/mcp` endpoints are created and the app structure is valid

#### Scenario: SSE transport configured independently

- **WHEN** transport mode is set to "sse"
- **THEN** the test verifies only `/sse` endpoint exists and app structure is valid

#### Scenario: Streamable-HTTP transport configured independently

- **WHEN** transport mode is set to "streamable-http"
- **THEN** the test verifies only `/mcp` endpoint exists and app structure is valid

#### Scenario: App has lifespan configured

- **WHEN** a combined app is created with any transport mode
- **THEN** the test verifies the app has lifespan configuration for proper startup/shutdown

#### Scenario: All transport modes create valid apps

- **WHEN** each transport mode ("both", "sse", "streamable-http") is used to create an app
- **THEN** the test verifies all modes create valid apps with routes configured

### Requirement: Pre-commit Test Execution

The system SHALL provide pre-commit hooks that automatically run unit tests before commits, with separate hooks for general unit tests and transport-specific tests.

#### Scenario: Unit tests run on commit

- **WHEN** files are committed and pre-commit hooks are installed
- **THEN** unit tests (excluding real and integration markers) run automatically

#### Scenario: Transport smoke tests run on transport file changes

- **WHEN** transport-related files are modified (fast_server.py, client_compat.py, settings.py, or transport test files)
- **THEN** the transport smoke test hook runs transport-specific tests automatically

#### Scenario: Fast test execution

- **WHEN** pre-commit hooks run tests
- **THEN** tests complete in under 15 seconds to avoid blocking commits (unit tests: ~11s, transport tests: ~11s)

#### Scenario: Test file changes trigger hook

- **WHEN** test files or source files are modified
- **THEN** the appropriate pre-commit hook runs tests based on file patterns

#### Scenario: CI/CD safe execution

- **WHEN** pre-commit hooks run tests
- **THEN** only tests marked as unit tests execute, excluding tests requiring Things 3

#### Scenario: Multiple pre-commit hooks

- **WHEN** pre-commit hooks are configured
- **THEN** both unit test hook and transport smoke test hook are available, each triggering on appropriate file changes
