## ADDED Requirements

### Requirement: UV Script Execution
The system SHALL provide UV script-based execution for the FastMCP server, allowing users to run the server using UV's native script management capabilities.

#### Scenario: Server startup with UV
- **WHEN** user runs `uv run server`
- **THEN** UV manages virtual environment, installs dependencies, and starts the FastMCP server

#### Scenario: Custom host and port configuration
- **WHEN** user sets environment variables `THINGS_FASTMCP_HOST` and `THINGS_FASTMCP_PORT`
- **THEN** UV script execution respects these configuration values (same as current bash script behavior)

#### Scenario: Configuration via .env file
- **WHEN** user creates a `.env` file with `THINGS_FASTMCP_HOST` and `THINGS_FASTMCP_PORT` values
- **THEN** the server automatically loads these values at startup

#### Scenario: Development mode execution
- **WHEN** user runs `uv run dev`
- **THEN** UV starts the server with development-friendly settings and logging

## MODIFIED Requirements

### Requirement: Server Execution Interface
The server execution interface SHALL use UV scripts instead of bash script wrapper for dependency management and virtual environment handling.

#### Scenario: Simplified execution
- **WHEN** user wants to start the server
- **THEN** they can use `uv run server` instead of `./run_things_fastmcp.sh`

#### Scenario: Environment variable support
- **WHEN** user sets `THINGS_FASTMCP_HOST=0.0.0.0` and `THINGS_FASTMCP_PORT=9000`
- **THEN** the server starts on the specified host and port

## REMOVED Requirements

### Requirement: Bash Script Execution
**Reason**: Replaced with UV-native script execution for better dependency management and simplified maintenance
**Migration**: Users should replace `./run_things_fastmcp.sh` commands with `uv run server`
