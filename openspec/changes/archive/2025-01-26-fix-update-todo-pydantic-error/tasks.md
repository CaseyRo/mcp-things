# Tasks: Fix update-todo Pydantic Validation Error

## Phase 1: Investigation & Root Cause Analysis

- [x] **1.1** Review `update_task` function in `src/things_mcp/fast_server.py`
  - Check all code paths and return statements
  - Verify no implicit `None` returns are possible
  - Document any edge cases

- [x] **1.2** Investigate FastMCP return type handling
  - Test how FastMCP processes `-> str` return annotations
  - Check if FastMCP expects `CallToolResult` vs. string
  - Review FastMCP documentation/examples for return type patterns

- [x] **1.3** Reproduce the error locally
  - Create a minimal test case with the exact JSON input provided
  - Verify the error occurs with current implementation
  - Capture error details and stack trace

## Phase 2: Fix Implementation

- [x] **2.1** Fix return type consistency
  - Ensure `update_task` always returns `str` (never `None`)
  - Verify `_error_result()` returns `str` (not `CallToolResult`)
  - Add explicit return statements if needed

- [x] **2.2** Add defensive checks
  - Add type guards to ensure return value is always a string
  - Add logging to track return values
  - Handle edge cases that might cause `None` returns

- [x] **2.3** Verify fix works
  - Test with the provided JSON input
  - Verify no Pydantic validation errors
  - Check that tool executes successfully

## Phase 3: Test Creation

- [x] **3.1** Create unit test in `tests/test_crud_todos.py`
  - Add test class `TestUpdateTodoPydanticValidation`
  - Use mocked dependencies (no real Things 3 required)
  - Test with exact JSON input format from user

- [x] **3.2** Test error reproduction
  - Create test that reproduces the Pydantic validation error
  - Verify test fails with current broken implementation
  - Document the error scenario

- [x] **3.3** Test fix verification
  - Update test to verify fix works
  - Test that function returns proper string value
  - Verify FastMCP can validate the return value

- [x] **3.4** Run test suite
  - Run `uv run pytest tests/test_crud_todos.py::TestUpdateTodoPydanticValidation -v`
  - Verify test passes with fix
  - Ensure no regressions in other tests

## Phase 4: Validation & Documentation

- [x] **4.1** Manual verification
  - Test with actual MCP client if possible
  - Verify tool works end-to-end
  - Document any additional findings

- [x] **4.2** Code review
  - Run `ruff check .` and fix any issues
  - Ensure code follows project conventions
  - Update docstrings if needed

- [x] **4.3** Update documentation
  - Add note about return type requirements for FastMCP tools
  - Document the fix in code comments if needed
