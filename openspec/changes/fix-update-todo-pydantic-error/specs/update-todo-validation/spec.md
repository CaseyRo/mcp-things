# Spec: update-todo Pydantic Validation Fix

## ADDED Requirements

### Requirement: update-todo Must Always Return String

**Description:** The `update-todo` FastMCP tool SHALL always return a string value that FastMCP can validate. The return value MUST never be `None` or any other type that causes Pydantic validation errors.

**Rationale:** FastMCP generates Pydantic models for tool outputs based on return type annotations. If a function annotated as `-> str` returns `None`, FastMCP's validation will fail with a type error.

#### Scenario: update-todo Returns String on Success
**Given** a valid todo ID and update parameters
**When** the `update-todo` tool is called successfully
**Then** the function returns a string message like `"Successfully updated todo with ID: {id}"`
**And** FastMCP can validate the return value without errors

#### Scenario: update-todo Returns String on Error
**Given** invalid parameters or a failed operation
**When** the `update-todo` tool encounters an error
**Then** the function returns a string error message (via `_error_result()`)
**And** the error message is prefixed with `⚠️`
**And** FastMCP can validate the return value without errors

#### Scenario: update-todo Never Returns None
**Given** any input to the `update-todo` tool
**When** the function executes (success or failure)
**Then** the return value is always a string (never `None`)
**And** all code paths have explicit return statements

### Requirement: Unit Test for Pydantic Validation

**Description:** A unit test SHALL exist that reproduces the Pydantic validation error and verifies the fix. The test MUST use mocked dependencies and be runnable locally without requiring Things 3 or a live MCP server.

**Rationale:** Without a local test, fixes must be deployed to production to verify, which is slow and risky. A local test allows rapid iteration and confidence in the fix.

#### Scenario: Test Reproduces Pydantic Error
**Given** the exact JSON input that triggers the error
**When** the test calls `update_task` with mocked dependencies
**And** the function returns `None` (simulating the bug)
**Then** the test verifies that FastMCP validation would fail
**And** the test documents the error scenario

#### Scenario: Test Verifies Fix
**Given** the fix is implemented
**When** the test calls `update_task` with the same input
**Then** the function returns a string value
**And** the test verifies FastMCP can validate the return value
**And** the test passes

#### Scenario: Test Uses Mocked Dependencies
**Given** the test is a unit test
**When** the test runs
**Then** it uses mocked Things 3 dependencies
**And** it uses mocked AppleScript/URL scheme execution
**And** it does not require Things 3 to be running
**And** it can run in CI/CD environments

## MODIFIED Requirements

### Requirement: update-todo Tool Reliability (Modified)

**Description:** The `update-todo` tool SHALL handle errors gracefully and return error messages. The tool SHALL **always** return a string value, even in error cases. The return value MUST be explicitly typed and validated to prevent Pydantic validation errors. All code paths SHALL have explicit return statements to guarantee a string is always returned.

**Existing:** The `update-todo` tool must handle errors gracefully and return error messages.

**Modification:** Enhanced to require explicit string returns in all code paths to prevent Pydantic validation errors.

#### Scenario: Explicit Return Type Guarantee
**Given** any execution path in `update_task`
**When** the function completes (success or exception)
**Then** an explicit `return` statement is executed
**And** the return value is always a `str` type
**And** no code path can implicitly return `None`

