# Design: Fix update-todo Pydantic Validation Error

## Problem Analysis

### Error Details

```
Error executing tool update-todo: 1 validation error for update_taskOutput
Input should be a valid dictionary or instance of update_taskOutput [type=model_type, input_value=None, input_type=NoneType]
```

### Root Cause Hypotheses

**Hypothesis 1: Implicit None Return**

- Python functions return `None` if no explicit return statement is executed
- Some code path in `update_task` might not have an explicit return
- FastMCP generates Pydantic model expecting `str`, but receives `None`

**Hypothesis 2: FastMCP Return Type Mismatch**

- FastMCP might expect `CallToolResult` directly, not strings
- String returns might need special handling
- Type annotation `-> str` might not match FastMCP's expectations

**Hypothesis 3: Exception Handling Issue**

- Exception might be raised but not caught properly
- Function might return `None` in exception case
- FastMCP validation happens before exception handling

### Current Implementation Review

```python
@mcp.tool(name="update-todo", annotations=TOOL_ANNOTATIONS["update-todo"])
def update_task(...) -> str:
    try:
        # ... validation and execution ...
        if not success:
            return _error_result("Error: Failed to update todo")
        return f"Successfully updated todo with ID: {id}"
    except Exception as e:
        logger.error(f"Error updating todo: {str(e)}")
        return _error_result(f"Error updating todo: {str(e)}")
```

**Observations:**

- All code paths appear to have explicit returns
- `_error_result()` should return `str` (recently changed)
- Exception handling has explicit return

## Solution Design

### Approach: Defensive Return Type Guarantee

1. **Explicit Return Type Validation**
   - Add runtime check to ensure return value is always `str`
   - Log warning if unexpected type is returned
   - Convert to string if needed as fallback

2. **FastMCP Compatibility**
   - Verify FastMCP expects string returns (not CallToolResult)
   - Ensure `_error_result()` returns plain string
   - Match pattern used by other working tools (`add-todo`, `add-project`)

3. **Test Strategy**
   - Create unit test that mocks FastMCP's validation
   - Test with exact JSON input that triggers the error
   - Verify return value is always a string

### Implementation Details

**Fix Location:** `src/things_mcp/fast_server.py`

**Changes:**

1. Add explicit return type check in `update_task`
2. Ensure `_error_result()` returns `str` (verify current implementation)
3. Add defensive return statement at end of function (should never execute)

**Test Location:** `tests/test_crud_todos.py`

**Test Structure:**

```python
class TestUpdateTodoPydanticValidation:
    """Test Pydantic validation for update-todo tool."""

    @pytest.mark.asyncio
    async def test_update_todo_returns_string_not_none(self, ...):
        """Verify update-todo always returns a string, never None."""
        # Test with exact JSON input from user
        # Verify return type is str
        # Verify FastMCP can validate the return value
```

## Risks & Mitigations

**Risk 1: FastMCP Behavior Change**

- **Mitigation:** Test with actual FastMCP instance if possible
- **Fallback:** Review FastMCP source code or documentation

**Risk 2: Breaking Other Tools**

- **Mitigation:** Only modify `update-todo`, keep other tools unchanged
- **Verification:** Run full test suite to ensure no regressions

**Risk 3: Test Doesn't Reproduce Issue**

- **Mitigation:** Create test that directly calls FastMCP validation
- **Alternative:** Test with mocked FastMCP introspection

## Open Questions

1. **Q:** Does FastMCP automatically wrap string returns in `CallToolResult`?
   - **A:** Need to verify by testing or reviewing FastMCP code

2. **Q:** Should we return `CallToolResult` directly instead of strings?
   - **A:** Check other working tools - they use `-> str`, so strings should work

3. **Q:** Is there a way to test FastMCP validation locally?
   - **A:** May need to create a minimal FastMCP server instance for testing

## Decision Log

- **Decision:** Use string returns (not CallToolResult) to match other tools
- **Rationale:** Other tools (`add-todo`, `add-project`) work with `-> str` annotation
- **Status:** Implemented in previous fix attempt, but error persists - need deeper investigation
