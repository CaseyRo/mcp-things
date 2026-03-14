## ADDED Requirements

### Requirement: Bearer token required for MCP endpoints

The server SHALL require a valid `Authorization: Bearer <api-key>` header on all requests to the `/mcp` endpoint. Requests without a valid bearer token SHALL receive a 401 Unauthorized response.

#### Scenario: Valid bearer token

- **WHEN** a client sends a request to `/mcp` with header `Authorization: Bearer <valid-key>`
- **THEN** the request is processed normally and the MCP response is returned

#### Scenario: Missing bearer token

- **WHEN** a client sends a request to `/mcp` without an `Authorization` header
- **THEN** the server responds with HTTP 401 Unauthorized

#### Scenario: Invalid bearer token

- **WHEN** a client sends a request to `/mcp` with header `Authorization: Bearer <wrong-key>`
- **THEN** the server responds with HTTP 401 Unauthorized

#### Scenario: Timing-safe comparison

- **WHEN** the server compares the provided token against the configured API key
- **THEN** it SHALL use constant-time comparison (`hmac.compare_digest`) to prevent timing attacks

### Requirement: API key configuration via environment variable

The server SHALL read the API key from the `THINGS_MCP_API_KEY` environment variable (or `.env` file via pydantic-settings).

#### Scenario: API key set in environment

- **WHEN** `THINGS_MCP_API_KEY` is set to a non-empty value
- **THEN** the server uses that value as the bearer token for authentication

#### Scenario: API key set in .env file

- **WHEN** `THINGS_MCP_API_KEY` is defined in the `.env` file
- **THEN** the server loads and uses that value via pydantic-settings

### Requirement: Auto-generate API key on first startup

The server SHALL generate a secure API key automatically if `THINGS_MCP_API_KEY` is not configured, and persist it to the `.env` file.

#### Scenario: No API key configured

- **WHEN** the server starts and `THINGS_MCP_API_KEY` is empty or unset
- **THEN** the server generates a cryptographically secure key in the format `tmcp_<urlsafe-base64-32>`
- **AND** writes `THINGS_MCP_API_KEY=<generated-key>` to the `.env` file with `0600` permissions
- **AND** uses the generated key for the current session

#### Scenario: API key already configured

- **WHEN** the server starts and `THINGS_MCP_API_KEY` is already set
- **THEN** the server does not generate or overwrite the existing key

### Requirement: Display API key on startup

The server SHALL print the active API key to the console on startup so the user can configure MCP clients.

#### Scenario: Startup key display

- **WHEN** the server starts successfully
- **THEN** it prints the API key to the console at WARNING level with clear formatting
- **AND** includes a note about configuring MCP clients with this key

#### Scenario: First-run key generation display

- **WHEN** the server auto-generates a new API key on first startup
- **THEN** it clearly indicates that a new key was generated and saved to `.env`

### Requirement: Dashboard remains unauthenticated

The `/dashboard` and `/dashboard/data` endpoints SHALL NOT require authentication.

#### Scenario: Dashboard without auth

- **WHEN** a client requests `/dashboard` without any `Authorization` header
- **THEN** the server returns the GTD Health Dashboard HTML with HTTP 200

#### Scenario: Dashboard data API without auth

- **WHEN** a client requests `/dashboard/data` without any `Authorization` header
- **THEN** the server returns the triage data JSON with HTTP 200

### Requirement: FastMCP native auth integration

The server SHALL use FastMCP's built-in `TokenVerifier` base class and pass it via `FastMCP(auth=verifier)` rather than implementing custom ASGI middleware.

#### Scenario: Auth provider registration

- **WHEN** the FastMCP server instance is created
- **THEN** a `BearerTokenVerifier` instance is passed as the `auth` parameter
- **AND** FastMCP handles bearer token extraction, middleware injection, and 401 responses
