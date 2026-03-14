## ADDED Requirements

### Requirement: AppleScript injection prevention via tag name validation

The server SHALL validate all tag name inputs against a safe character pattern before passing them to AppleScript. Tag names SHALL only contain word characters, spaces, hyphens, and the `@` prefix. AppleScript tag lists SHALL use proper list syntax instead of string interpolation.

#### Scenario: Valid tag name accepted

- **WHEN** a tool receives tag names containing only word characters, spaces, hyphens, or `@` prefix (e.g., `@computer`, `my-tag`, `Work Tasks`)
- **THEN** the tag names are accepted and passed to AppleScript using proper list construction

#### Scenario: Malicious tag name rejected

- **WHEN** a tool receives a tag name containing characters outside `[@\w\s\-]` (e.g., `"; do shell script "rm -rf /"`)
- **THEN** the server SHALL reject the input with a ToolError before any AppleScript execution

#### Scenario: AppleScript list construction

- **WHEN** multiple tags are passed to an AppleScript operation
- **THEN** they SHALL be constructed as a proper AppleScript list `{"tag1", "tag2"}` rather than embedded in a single string literal

### Requirement: Sensitive file permissions enforced on startup

The server SHALL verify and correct file permissions for all sensitive files on every startup, regardless of how the files were originally created.

#### Scenario: .env file permissions

- **WHEN** the server starts and the `.env` file exists with permissions more permissive than `0600`
- **THEN** the server corrects the permissions to `0600` and logs a warning

#### Scenario: Legacy config file permissions

- **WHEN** the server starts and `~/.things-mcp/config.json` exists with permissions more permissive than `0600`
- **THEN** the server corrects the file to `0600` and the directory to `0700`

#### Scenario: Log file permissions

- **WHEN** the server creates or opens log files
- **THEN** log files SHALL have `0600` permissions and the log directory SHALL have `0700` permissions

#### Scenario: DLQ file permissions

- **WHEN** the DeadLetterQueue writes to `things_dlq.json`
- **THEN** the file SHALL have `0600` permissions

### Requirement: Error messages sanitized for MCP clients

The server SHALL NOT return raw Python exception messages to MCP clients. Error responses SHALL contain only generic descriptions without internal file paths, SQL errors, or configuration details.

#### Scenario: Internal exception during tool execution

- **WHEN** a tool raises an unexpected exception (not a deliberately-raised ToolError)
- **THEN** the server returns a generic error message (e.g., "Failed to fetch tasks. Check server logs for details.")
- **AND** logs the full exception with traceback at ERROR level for debugging

#### Scenario: Intentional validation error

- **WHEN** a tool raises a ToolError with a deliberately crafted message (e.g., "Invalid date format")
- **THEN** the server returns that message to the client as-is

### Requirement: Log redaction uses URL-boundary-aware patterns

The log redaction system SHALL use URL parameter boundary characters (`&`, whitespace) as delimiters rather than `[^;,.]+` which crosses parameter boundaries.

#### Scenario: Title followed by auth-token in URL

- **WHEN** a log message contains `title=Buy milk&auth-token=SECRET`
- **THEN** the title pattern redacts only `Buy milk` (stops at `&`)
- **AND** the auth-token pattern independently redacts `SECRET`

#### Scenario: Auth-token without preceding title

- **WHEN** a log message contains `auth-token=SECRET&completed=true`
- **THEN** the auth-token pattern redacts `SECRET` (stops at `&`)

### Requirement: Dashboard input validation

The dashboard endpoints SHALL validate query parameters and return safe defaults for invalid input rather than raising unhandled exceptions.

#### Scenario: Invalid days parameter

- **WHEN** a request to `/dashboard` or `/dashboard/data` includes `?days=abc`
- **THEN** the server returns the dashboard with the default period (30 days) instead of a 500 error

#### Scenario: Negative days parameter

- **WHEN** a request includes `?days=-5`
- **THEN** the server clamps the value to `0` (all-time)

#### Scenario: Excessive days parameter

- **WHEN** a request includes `?days=99999`
- **THEN** the server clamps the value to `365`

### Requirement: PII redaction in triage data

The triage tracker SHALL NOT store personally identifiable information in its history file or serve it via the dashboard data API.

#### Scenario: Delegated task with person name

- **WHEN** `delegate-task` records a triage action with `delegated_to: "Bob Smith"`
- **THEN** the triage tracker stores the action without the person's name (redacted or omitted from `action_details`)

### Requirement: DeadLetterQueue content sanitization

The DeadLetterQueue SHALL strip task content fields before persisting failed operations to disk.

#### Scenario: Failed operation with task content

- **WHEN** a URL scheme operation fails and is added to the DLQ with params containing `title`, `notes`, or `checklist-items`
- **THEN** those fields are replaced with `[REDACTED]` before writing to `things_dlq.json`

### Requirement: Dashboard security headers

The dashboard HTTP responses SHALL include security headers to prevent clickjacking and content-type sniffing.

#### Scenario: Dashboard HTML response headers

- **WHEN** a client requests `/dashboard`
- **THEN** the response includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and a `Content-Security-Policy` header

#### Scenario: Dashboard JSON API response headers

- **WHEN** a client requests `/dashboard/data`
- **THEN** the response includes the same security headers

### Requirement: Dashboard uses safe DOM manipulation

The dashboard JavaScript SHALL use `textContent` instead of `innerHTML` for rendering text-only data to prevent XSS if data sources change.

#### Scenario: Category labels rendered

- **WHEN** the dashboard renders category names or action labels from triage data
- **THEN** it uses `textContent` or equivalent safe DOM API instead of `innerHTML`

### Requirement: show-in-app id parameter validation

The `show-in-app` tool SHALL validate the `id` parameter format before passing it to the Things URL scheme.

#### Scenario: Valid Things UUID

- **WHEN** `show-in-app` receives an `id` matching Things UUID format
- **THEN** the request is processed normally

#### Scenario: Valid named list

- **WHEN** `show-in-app` receives a known list name (`inbox`, `today`, `upcoming`, `anytime`, `someday`, `logbook`)
- **THEN** the request is processed normally

#### Scenario: Invalid id format

- **WHEN** `show-in-app` receives an `id` that is neither a valid UUID nor a known list name
- **THEN** the server returns a ToolError before making any URL scheme call
