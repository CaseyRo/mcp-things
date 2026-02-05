# Fix update-todo Pydantic Validation Error

## Summary

The `update-todo` FastMCP tool is failing with a Pydantic validation error:

```
Error executing tool update-todo: 1 validation error for update_taskOutput
Input should be a valid dictionary or instance of update_taskOutput [type=model_type, input_value=None, input_type=NoneType]
```

This error occurs when FastMCP tries to validate the tool's return value against a generated Pydantic model, but receives `None` instead of the expected type.

## Why This Change

**Problem:**

- FastMCP generates Pydantic models for tool outputs based on return type annotations
- The `update_task` function is annotated as `-> str`, but FastMCP's introspection/validation is receiving `None`
- This prevents the tool from working correctly when called via MCP
- No local test exists to reproduce and verify the fix

**Impact:**

- Users cannot update todos via the MCP interface
- The error is cryptic and doesn't clearly indicate the root cause
- Without a local test, fixes must be deployed to production to verify

## What Changes

1. **Root Cause Investigation:**
   - Investigate why FastMCP is receiving `None` instead of a string
   - Check if there are any code paths that could return `None` implicitly
   - Verify FastMCP's handling of string return types vs. CallToolResult

2. **Fix Implementation:**
   - Ensure all code paths in `update_task` explicitly return a string
   - Verify `_error_result()` returns a string (not CallToolResult)
   - Add explicit return type guards if needed

3. **Test Creation:**
   - Create a unit test that reproduces the Pydantic validation error
   - Test with the exact JSON input format provided by the user
   - Verify the tool returns a proper string value that FastMCP can validate
   - Add test to existing test suite in `tests/test_crud_todos.py`

## Non-Goals

- Changing FastMCP's validation behavior (work within FastMCP's expectations)
- Modifying other tools (focus only on `update-todo`)
- Adding integration tests that require Things 3 (unit test with mocked dependencies is sufficient)

## Success Criteria

1. ✅ `update-todo` tool executes successfully with the provided JSON input
2. ✅ No Pydantic validation errors occur
3. ✅ Unit test exists that reproduces the issue and verifies the fix
4. ✅ Test can be run locally without deploying to production
5. ✅ All existing tests continue to pass
