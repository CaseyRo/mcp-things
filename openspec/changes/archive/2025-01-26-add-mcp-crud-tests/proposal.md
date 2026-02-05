# Change: Add MCP CRUD Tests

## Why

The Things MCP server currently lacks automated tests to verify that basic CRUD (Create, Read, Update, Delete) operations work correctly. Without tests, we cannot confidently verify that:

1. Tool handlers correctly process parameters and return expected results
2. Data integrity is maintained across operations (create → read → update → verify)
3. Error handling works correctly for invalid inputs
4. Changes to the codebase don't break existing functionality

Adding a comprehensive test suite will improve code quality, enable safe refactoring, and catch regressions early.

## What Changes

- **Test Infrastructure**: Create `tests/` directory with pytest test files for MCP tool operations
- **Dual Test Strategy**: Implement both unit tests (mocked, CI/CD safe) and real integration tests (Things 3, dev only)
- **CRUD Test Suite**: Implement tests for basic CRUD operations:
  - **Create**: Test `add-todo` and `add-project` tools (both mocked and real)
  - **Read**: Test `get-todos`, `get-projects`, `get-areas`, `get-tags`, and list view tools (both mocked and real)
  - **Update**: Test `update-todo` and `update-project` tools (both mocked and real)
  - **Delete/Complete**: Test completion and cancellation via update operations
- **Test Utilities**: Create fixtures and helpers for:
  - Mocking Things 3 interactions (things-py library calls) - for unit tests
  - Mocking AppleScript execution - for unit tests
  - Mocking URL scheme execution - for unit tests
  - Real Things 3 integration with automatic cleanup - for integration tests
  - UUID tracking and deletion of test data
- **Integration Tests**: Add tests that verify end-to-end workflows (create → read → update → verify) with both mocked and real Things 3
- **Error Handling Tests**: Verify proper error responses for invalid inputs and edge cases
- **Test Commands**: Add separate commands for unit tests (`test`, `test:unit`) and real integration tests (`test:dev`, `test:integration`)

## Impact

- **Affected specs**: `mcp-testing` (new capability)
- **Affected code**:
  - New `tests/` directory with test files
  - `tests/conftest.py` - pytest fixtures and test utilities
  - `tests/test_crud_todos.py` - Todo CRUD tests
  - `tests/test_crud_projects.py` - Project CRUD tests
  - `tests/test_read_operations.py` - Read operation tests
  - `tests/test_integration.py` - End-to-end integration tests
- **Development Workflow**:
  - Unit tests (mocked) run in CI/CD via `pytest` or `uv run test` command
  - Real integration tests run locally via `uv run test:dev` command (requires Things 3)
- **Code Quality**: Enables safe refactoring and regression detection
- **Test Data Management**: Real integration tests automatically clean up created items, ensuring no test data remains in Things 3
