## ADDED Requirements

### Requirement: Test Infrastructure

The system SHALL provide a test infrastructure that enables automated testing of MCP tool operations with both mocked dependencies (for CI/CD) and real Things 3 integration (for local development).

#### Scenario: Test infrastructure setup

- **WHEN** tests are executed via `pytest`
- **THEN** shared fixtures and utilities are available for mocking Things 3 interactions, AppleScript execution, and URL scheme operations

#### Scenario: Real integration test infrastructure

- **WHEN** real integration tests are executed
- **THEN** fixtures are available for tracking created items and automatically cleaning them up after tests complete

#### Scenario: Test organization

- **WHEN** tests are organized by operation type and entity
- **THEN** tests are grouped into logical files (CRUD operations, read operations, integration tests) for maintainability

### Requirement: Create Operation Tests

The system SHALL provide tests that verify todo and project creation operations work correctly.

#### Scenario: Create todo with minimal parameters

- **WHEN** `add-todo` is called with only a title parameter
- **THEN** the test verifies the tool handler processes the request and returns a success response indicating the todo was created

#### Scenario: Create todo with all parameters

- **WHEN** `add-todo` is called with title, notes, when, tags, and list_title parameters
- **THEN** the test verifies all parameters are correctly processed and the response indicates successful creation

#### Scenario: Create todo error handling

- **WHEN** `add-todo` is called with missing required parameters (e.g., no title)
- **THEN** the test verifies an appropriate error response is returned

#### Scenario: Create project with minimal parameters

- **WHEN** `add-project` is called with only a title parameter
- **THEN** the test verifies the tool handler processes the request and returns a success response

#### Scenario: Create project with all parameters

- **WHEN** `add-project` is called with title, notes, when, deadline, tags, area_id, and todos parameters
- **THEN** the test verifies all parameters are correctly processed and the response indicates successful creation

#### Scenario: Create project error handling

- **WHEN** `add-project` is called with missing required parameters
- **THEN** the test verifies an appropriate error response is returned

### Requirement: Read Operation Tests

The system SHALL provide tests that verify read operations (queries, list views, searches) return correct data.

#### Scenario: Get todos without filters

- **WHEN** `get-todos` is called without project_uuid filter
- **THEN** the test verifies the response contains formatted todo data

#### Scenario: Get todos with project filter

- **WHEN** `get-todos` is called with a project_uuid parameter
- **THEN** the test verifies only todos belonging to that project are returned

#### Scenario: Get projects with include_items

- **WHEN** `get-projects` is called with include_items=True
- **THEN** the test verifies the response includes project items (todos) in the formatted output

#### Scenario: Get projects without include_items

- **WHEN** `get-projects` is called with include_items=False
- **THEN** the test verifies the response excludes project items from the formatted output

#### Scenario: List view operations

- **WHEN** list view tools are called (`get-inbox`, `get-today`, `get-upcoming`, `get-anytime`, `get-someday`, `get-logbook`, `get-trash`)
- **THEN** the test verifies each tool returns formatted data matching the expected list view

#### Scenario: Get tagged items

- **WHEN** `get-tagged-items` is called with a valid tag name
- **THEN** the test verifies only items with that tag are returned

#### Scenario: Search todos

- **WHEN** `search-todos` is called with a query string
- **THEN** the test verifies the response contains todos matching the search query

#### Scenario: Advanced search

- **WHEN** `search-advanced` is called with multiple filter parameters (status, dates, tags, area, type)
- **THEN** the test verifies the response contains todos matching all specified criteria

### Requirement: Update Operation Tests

The system SHALL provide tests that verify todo and project update operations work correctly.

#### Scenario: Update todo title

- **WHEN** `update-todo` is called with a todo id and new title
- **THEN** the test verifies the tool handler processes the update and returns a success response

#### Scenario: Update todo with multiple fields

- **WHEN** `update-todo` is called with id, title, notes, when, deadline, and tags parameters
- **THEN** the test verifies all fields are correctly updated

#### Scenario: Update todo tags

- **WHEN** `update-todo` is called with id and tags parameter
- **THEN** the test verifies tags are correctly applied to the todo

#### Scenario: Complete todo

- **WHEN** `update-todo` is called with id and completed=True
- **THEN** the test verifies the todo is marked as completed

#### Scenario: Cancel todo

- **WHEN** `update-todo` is called with id and canceled=True
- **THEN** the test verifies the todo is marked as canceled

#### Scenario: Update todo error handling

- **WHEN** `update-todo` is called with missing id or invalid id
- **THEN** the test verifies an appropriate error response is returned

#### Scenario: Update project

- **WHEN** `update-project` is called with project id and update parameters
- **THEN** the test verifies the project is correctly updated

#### Scenario: Update project error handling

- **WHEN** `update-project` is called with missing id or invalid id
- **THEN** the test verifies an appropriate error response is returned

### Requirement: Integration Tests

The system SHALL provide tests that verify end-to-end workflows combining multiple operations, both with mocked dependencies and real Things 3 integration.

#### Scenario: Create-read-update workflow (mocked)

- **WHEN** a todo is created, then read, then updated, then read again (using mocks)
- **THEN** the test verifies the complete workflow succeeds and data integrity is maintained

#### Scenario: Project with todos workflow (mocked)

- **WHEN** a project is created, todos are added to it, and the project is read with include_items (using mocks)
- **THEN** the test verifies the project contains the expected todos

#### Scenario: Tag association workflow (mocked)

- **WHEN** a todo is created with tags, then get-tagged-items is called with those tags (using mocks)
- **THEN** the test verifies the todo appears in the tagged items results

#### Scenario: Search workflow (mocked)

- **WHEN** multiple todos are created with different titles, then search-todos is called (using mocks)
- **THEN** the test verifies search returns the expected matching todos

### Requirement: Real Integration Tests with Things 3

The system SHALL provide integration tests that verify operations against a real Things 3 installation, with automatic cleanup of test data.

#### Scenario: Real create-read-update workflow

- **WHEN** a todo is created in real Things 3, then read, then updated, then read again
- **THEN** the test verifies the complete workflow succeeds, data integrity is maintained, and the test todo is automatically deleted after the test completes

#### Scenario: Real project with todos workflow

- **WHEN** a project is created in real Things 3, todos are added to it, and the project is read with include_items
- **THEN** the test verifies the project contains the expected todos, and all test data (project and todos) is automatically deleted after the test completes

#### Scenario: Real tag association workflow

- **WHEN** a todo is created with tags in real Things 3, then get-tagged-items is called with those tags
- **THEN** the test verifies the todo appears in the tagged items results, and the test todo is automatically deleted after the test completes

#### Scenario: Real search workflow

- **WHEN** multiple todos are created with different titles in real Things 3, then search-todos is called
- **THEN** the test verifies search returns the expected matching todos, and all test todos are automatically deleted after the test completes

#### Scenario: Automatic cleanup of test data

- **WHEN** a real integration test creates items in Things 3
- **THEN** the test framework automatically tracks created item UUIDs and deletes them after the test completes, ensuring no test data remains in Things 3

#### Scenario: Graceful handling when Things 3 unavailable

- **WHEN** a real integration test is executed but Things 3 is not available
- **THEN** the test is skipped gracefully without failing the test suite

### Requirement: Error Handling Tests

The system SHALL provide tests that verify proper error handling for invalid inputs and edge cases.

#### Scenario: Invalid UUID format

- **WHEN** a tool is called with an invalid UUID format
- **THEN** the test verifies an appropriate error response is returned

#### Scenario: Missing required parameters

- **WHEN** a tool is called without required parameters
- **THEN** the test verifies an error response indicating missing parameters

#### Scenario: Empty string parameters

- **WHEN** a tool is called with empty string values for parameters
- **THEN** the test verifies the tool handles empty strings appropriately (either accepts or rejects with error)

#### Scenario: Special characters in input

- **WHEN** a tool is called with special characters in title or notes
- **THEN** the test verifies the tool handles special characters correctly

#### Scenario: Invalid date formats

- **WHEN** a tool is called with invalid date format for when or deadline parameters
- **THEN** the test verifies an appropriate error response is returned

#### Scenario: Things app unavailable

- **WHEN** a write operation is attempted but Things app is not available (mocked)
- **THEN** the test verifies the tool returns an appropriate error response

### Requirement: Test Execution and Coverage

The system SHALL provide a test suite that can be executed reliably with separate commands for unit tests (CI/CD safe) and real integration tests (dev only), and provides coverage metrics.

#### Scenario: Unit test execution (CI/CD safe)

- **WHEN** `pytest` or `uv run test` is run from the project root
- **THEN** only unit tests (mocked) execute and report pass/fail status, excluding real integration tests that require Things 3

#### Scenario: Real integration test execution (dev only)

- **WHEN** `uv run test:dev` is run from the project root
- **THEN** both unit tests and real integration tests execute, including tests that require Things 3

#### Scenario: Explicit unit test command

- **WHEN** `uv run test:unit` is run
- **THEN** only unit tests (mocked) are executed, explicitly excluding real integration tests

#### Scenario: Explicit integration test command

- **WHEN** `uv run test:integration` is run
- **THEN** only real integration tests (requiring Things 3) are executed

#### Scenario: Test coverage

- **WHEN** `pytest --cov` is run
- **THEN** coverage report shows >80% coverage on handler functions in `handlers.py`

#### Scenario: Test categorization

- **WHEN** tests are marked with pytest markers (unit, integration, real, slow)
- **THEN** tests can be selectively executed using marker filters

#### Scenario: CI/CD test execution

- **WHEN** tests are run in a CI/CD environment where Things 3 is not available
- **THEN** the default test command runs only unit tests (mocked), and real integration tests are automatically skipped
