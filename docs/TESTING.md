# Testing Guide

This document describes the test suite for the Things MCP server.

## Test Structure

The test suite is organized into several files:

- `tests/conftest.py` - Shared fixtures and test utilities
- `tests/test_crud_todos.py` - Todo CRUD operation tests
- `tests/test_crud_projects.py` - Project CRUD operation tests
- `tests/test_read_operations.py` - Read/list/search operation tests
- `tests/test_integration.py` - End-to-end workflow tests
- `tests/test_error_handling.py` - Error handling and edge case tests

## Test Types

### Unit Tests (Mocked)

Unit tests use mocked dependencies and are fast, portable, and CI/CD safe. They don't require Things 3 to be installed.

**Markers**: `@pytest.mark.unit` (default)

**Run**: `uv run test` or `pytest -m unit`

### Real Integration Tests

Real integration tests interact with an actual Things 3 installation. They automatically clean up test data after completion.

**Markers**: `@pytest.mark.real`, `@pytest.mark.integration`, `@pytest.mark.slow`

**Requirements**:
- macOS with Things 3 installed
- Things 3 must be running
- Scripting permissions enabled in System Preferences

**Run**: `pytest -m real`

**Note**: Real integration tests are automatically skipped if Things 3 is not available.

## Running Tests

### All Tests (Including Real Integration)

```bash
# Run all tests including real Things 3 integration (requires Things 3)
# Note: 'uv run test' may suppress output; use direct pytest command for visible output
uv run python -m pytest tests
```

### Unit Tests Only (CI/CD Safe)

```bash
# Run only unit tests (excludes real integration tests)
uv run python -m pytest tests -m "not real"
```

### Real Integration Tests Only

```bash
# Run only real integration tests
uv run python -m pytest tests -m real
```

### With Coverage

```bash
# Run tests with coverage report
pytest --cov=src/things_mcp --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Markers

Tests are categorized using pytest markers:

- `unit` - Fast unit tests with mocked dependencies (default, CI/CD safe)
- `integration` - Tests that verify multiple operations together
- `real` - Real integration tests requiring Things 3 (dev only)
- `slow` - Tests that may take longer (real integration tests)

### Running Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests (mocked)
pytest -m integration

# Run only real integration tests
pytest -m real

# Skip slow tests
pytest -m "not slow"

# Skip real integration tests
pytest -m "not real"
```

## Automatic Cleanup

Real integration tests automatically clean up test data using the `test_data_tracker` fixture. All created todos and projects are tracked and deleted after each test completes.

**Test Data Naming**: Test items are created with unique identifiers using the pattern `MCP-TEST-{timestamp}-{random}` to avoid conflicts.

## Test Coverage

The test suite aims for >80% coverage on handler functions in `src/things_mcp/handlers.py`.

View coverage:

```bash
pytest --cov=src/things_mcp --cov-report=term-missing
```

## Test Results History

Test results are automatically captured and stored in `test-results/test-results.md` after each test run. The file contains the last 3 test runs with:

- **Summary statistics** (total, passed, failed, skipped, errors)
- **Failed tests** with error messages
- **Skipped tests** with skip reasons
- **Test breakdown by marker** (unit, integration, real, etc.)
- **Duration** for each run

**View results:**

```bash
# View the test results history
cat test-results/test-results.md

# Or open in your editor
open test-results/test-results.md
```

The results file is automatically updated after each test run and maintains a rolling history of the last 3 runs.

## CI/CD

In CI/CD environments, only unit tests (mocked) are run. Real integration tests are automatically excluded via the default pytest configuration (`-m "not real"`).

## Troubleshooting

### Tests Fail with "Things 3 not available"

Real integration tests require Things 3 to be installed and running. If you see this error:

1. Ensure Things 3 is installed
2. Launch Things 3
3. Enable scripting permissions in System Preferences > Security & Privacy > Privacy > Automation

### Tests Leave Data in Things 3

If test data remains in Things 3 after running tests:

1. Check that the `test_data_tracker` fixture is being used
2. Verify Things 3 is responding to AppleScript commands
3. Manually delete test items with titles starting with "MCP-TEST-"

### Import Errors

If you see import errors when running tests:

1. Ensure you're in the project root directory
2. Install test dependencies: `uv sync`
3. Verify Python path includes the `src` directory

## Writing New Tests

### Unit Test Example

```python
@pytest.mark.unit
class TestMyFeature:
    @pytest.mark.asyncio
    async def test_my_feature(self, mock_things, mock_applescript, mock_utils):
        # Setup mocks
        mock_applescript.return_value = "test-id"

        # Execute
        result = await handlers.handle_tool_call("add-todo", {"title": "Test"})

        # Verify
        assert_text_content(result, "Created new todo")
```

### Real Integration Test Example

```python
@pytest.mark.real
@pytest.mark.integration
@pytest.mark.slow
class TestMyFeatureReal:
    @pytest.mark.asyncio
    async def test_my_feature_real(self, test_data_tracker, things_available):
        if not things_available:
            pytest.skip("Things 3 not available")

        test_title = generate_test_title("MCP-TEST")

        # Execute
        result = await handlers.handle_tool_call(
            "add-todo",
            {"title": test_title}
        )

        # Track for cleanup
        # Extract UUID from result and add to tracker
        # test_data_tracker.add_todo(todo_id)

        # Verify
        assert_text_content(result, "Created new todo")
```

## Best Practices

1. **Use fixtures** - Leverage `conftest.py` fixtures for common setup
2. **Mock external dependencies** - Mock things-py, AppleScript, and URL scheme for unit tests
3. **Track test data** - Always use `test_data_tracker` for real integration tests
4. **Use unique identifiers** - Generate unique test titles to avoid conflicts
5. **Mark tests appropriately** - Use correct markers (`unit`, `real`, `integration`, `slow`)
6. **Clean up** - Ensure test data is cleaned up in real integration tests

