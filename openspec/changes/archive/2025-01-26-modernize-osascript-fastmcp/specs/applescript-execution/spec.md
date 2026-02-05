## MODIFIED Requirements

### Requirement: AppleScript Execution

The system SHALL execute AppleScript commands to interact with Things 3 without bringing the application to the foreground or interrupting user workflow.

The system SHALL wrap all AppleScript commands targeting Things 3 with `without activating` clause to prevent the application from being brought to the foreground.

The system SHALL use `ignoring application responses` where appropriate for operations that do not require return values, allowing faster background execution.

#### Scenario: Todo creation via AppleScript

- **WHEN** a todo is created using `add_todo_direct()` via AppleScript
- **THEN** Things 3 remains in the background and does not appear in the foreground
- **AND** the todo is successfully created

#### Scenario: Todo update via AppleScript

- **WHEN** a todo is updated using `update_todo_direct()` via AppleScript
- **THEN** Things 3 remains in the background and does not appear in the foreground
- **AND** the todo is successfully updated

#### Scenario: Tag creation via AppleScript

- **WHEN** tags are created using `ensure_tags_exist()` via AppleScript
- **THEN** Things 3 remains in the background and does not appear in the foreground
- **AND** the tags are successfully created

#### Scenario: App state check via AppleScript

- **WHEN** the system checks if Things is running using `is_things_running()` via AppleScript
- **THEN** Things 3 remains in the background and does not appear in the foreground
- **AND** the running status is correctly returned

#### Scenario: Version detection via AppleScript

- **WHEN** the system detects Things version using `detect_things_version()` via AppleScript
- **THEN** Things 3 remains in the background and does not appear in the foreground
- **AND** the version is correctly returned

## ADDED Requirements

### Requirement: Background Execution Wrapper

The system SHALL provide a mechanism to wrap AppleScript commands with background execution directives.

The `run_applescript()` function SHALL automatically wrap commands targeting Things 3 with `without activating` to ensure background execution.

The system SHALL check the `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable to allow disabling background execution for debugging purposes.

#### Scenario: Background wrapper application

- **WHEN** `run_applescript()` is called with a script targeting "Things3"
- **AND** `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` is not set
- **THEN** the script is automatically wrapped with `tell application "Things3" without activating ... end tell`
- **AND** the application does not activate

#### Scenario: Background execution disabled via environment variable

- **WHEN** `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` environment variable is set to any non-empty value
- **AND** `run_applescript()` is called with a script targeting "Things3"
- **THEN** the script executes without background wrapping (allows Things to activate)
- **AND** existing foreground execution behavior is preserved

#### Scenario: Non-Things scripts

- **WHEN** `run_applescript()` is called with a script targeting an application other than Things3
- **THEN** the script executes normally without background wrapping
- **AND** existing behavior is preserved
