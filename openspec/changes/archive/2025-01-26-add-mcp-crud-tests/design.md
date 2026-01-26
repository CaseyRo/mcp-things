# Design: MCP CRUD Test Suite

## Context

The Things MCP server provides 19 tools for interacting with Things 3, but currently has no automated tests. This design document outlines the testing strategy for adding comprehensive CRUD tests that verify tool functionality without requiring a live Things 3 installation.

## Goals / Non-Goals

### Goals
- Verify basic CRUD operations work correctly for todos and projects
- Test error handling and edge cases
- Enable safe refactoring through regression detection
- Provide fast, reliable unit tests that don't depend on Things 3 being installed (for CI/CD)
- Provide real integration tests that verify actual Things 3 interactions (for local development)
- Ensure test data is automatically cleaned up after real integration tests
- Achieve >80% code coverage on handler functions

### Non-Goals
- Testing Things 3 app itself (that's Cultured Code's responsibility)
- Running real integration tests in CI/CD (Things 3 not available)
- Performance/load testing (out of scope for initial test suite)
- Testing UI interactions (MCP tools don't interact with UI directly)

## Decisions

### Decision: Dual Test Strategy (Mocked + Real Integration)
**Rationale**: Provide both fast, portable unit tests (for CI/CD) and real integration tests (for local development) to ensure comprehensive coverage.

**Unit Tests (Mocked)**:
- Fast, reliable, and portable - run anywhere Python runs
- Mock `things` library calls (things-py) using `unittest.mock` or `pytest-mock`
- Mock `subprocess.run()` for AppleScript execution
- Mock `url_scheme.execute_url()` for URL scheme operations
- Use pytest fixtures to provide consistent mock setup
- Marked with `@pytest.mark.unit` (default)

**Integration Tests (Real Things 3)**:
- Verify actual Things 3 interactions on macOS
- Require Things 3 to be installed and running
- Automatically create test data with unique identifiers
- Automatically clean up test data after each test (delete created todos/projects)
- Marked with `@pytest.mark.integration` and `@pytest.mark.real`
- Only run in local development environment (not CI/CD)

**Implementation**:
- Use pytest fixtures with `autouse=True` for cleanup
- Track created item UUIDs during tests
- Use Things URL scheme or AppleScript to delete test items after test completion
- Skip real integration tests if Things 3 is not available (graceful degradation)

### Decision: Test Structure Organization
**Rationale**: Organize tests by operation type (CRUD) and entity type (todos, projects) for clarity and maintainability.

**Structure**:
```
tests/
├── conftest.py              # Shared fixtures and utilities
├── test_crud_todos.py       # Todo CRUD operations
├── test_crud_projects.py    # Project CRUD operations
├── test_read_operations.py  # All read/list/search operations
├── test_integration.py      # End-to-end workflows
└── test_utils.py            # Test helper functions
```

**Alternatives Considered**:
1. **One file per tool**: Too many files, harder to see related operations together.
2. **One file for all tests**: Too large, hard to navigate.
3. **By operation type**: Chosen - balances organization with maintainability.

### Decision: Use pytest Markers for Test Categorization
**Rationale**: Allows selective test execution (unit vs integration, mocked vs real).

**Markers**:
- `@pytest.mark.unit` - Fast unit tests with mocks (default, CI/CD safe)
- `@pytest.mark.integration` - Tests that verify multiple operations together
- `@pytest.mark.real` - Real integration tests requiring Things 3 (dev only)
- `@pytest.mark.slow` - Tests that may take longer (real integration tests)

**Usage**:
```bash
pytest -m unit              # Run only unit tests (CI/CD safe)
pytest -m "not real"        # Skip real integration tests
pytest -m integration       # Run integration tests (mocked)
pytest -m real              # Run real Things 3 integration tests (dev only)
```

### Decision: Separate Test Commands for Dev vs CI/CD
**Rationale**: Provide distinct commands for unit tests (CI/CD safe) and integration tests (dev only, requires Things 3).

**Commands**:
- `pytest` or `uv run test` - Run all unit tests (mocked, CI/CD safe)
- `uv run test:dev` - Run all tests including real Things 3 integration tests (dev only)
- `uv run test:unit` - Explicitly run only unit tests
- `uv run test:integration` - Run only real integration tests (requires Things 3)

**Implementation**:
- Add scripts to `pyproject.toml` under `[project.scripts]` or `[tool.hatch.envs.default.scripts]`
- `test:dev` command uses `pytest -m "unit or real"` to include both
- `test:integration` command uses `pytest -m real` for real Things 3 tests only
- CI/CD runs default `pytest` which excludes real integration tests

### Decision: Mock Data Structure
**Rationale**: Use realistic but simplified data structures that match things-py library responses.

**Mock Todo Structure**:
```python
{
    "uuid": "test-todo-uuid-123",
    "type": "to-do",
    "title": "Test Todo",
    "notes": "Test notes",
    "status": "open",
    "tags": ["test", "mcp"],
    "when": "2025-01-01",
    "deadline": None,
    "project": None,
    "area": None,
}
```

**Mock Project Structure**:
```python
{
    "uuid": "test-project-uuid-456",
    "type": "project",
    "title": "Test Project",
    "notes": "Project notes",
    "status": "open",
    "tags": ["project"],
    "when": None,
    "deadline": None,
    "area": None,
    "items": [],  # List of todos in project
}
```

### Decision: Test Assertions Strategy
**Rationale**: Verify both success responses and error responses match expected MCP format.

**Success Assertions**:
- Response is `list[types.TextContent]`
- Response text contains expected data (title, UUID, etc.)
- Response format matches formatter output

**Error Assertions**:
- Response is `list[types.TextContent]` with `isError=True` (via `_error_result()`)
- Error message is informative and user-friendly
- Invalid parameters are properly validated

## Risks / Trade-offs

### Risk: Mock Data Drift
**Mitigation**: Keep mock data structures aligned with things-py library by checking library updates and test failures.

### Risk: Over-Mocking
**Mitigation**: Focus on mocking external dependencies (things-py, subprocess, URL execution) but test actual handler logic.

### Risk: False Confidence
**Mitigation**: Real integration tests verify actual Things 3 behavior. Unit tests with mocks provide fast feedback for CI/CD.

### Risk: Test Data Pollution
**Mitigation**: Real integration tests automatically clean up created items using pytest fixtures with `autouse=True`. Track all created UUIDs and delete them in teardown.

### Risk: Real Tests Failing Due to Things 3 State
**Mitigation**: Use unique identifiers (timestamps, random strings) in test data to avoid conflicts. Skip real tests gracefully if Things 3 is unavailable.

### Trade-off: Speed vs Realism
**Decision**: Provide both - fast mocked unit tests for CI/CD and real integration tests for local development. Best of both worlds.

## Migration Plan

1. **Phase 1**: Create test infrastructure (conftest.py, fixtures for both mocked and real tests)
2. **Phase 2**: Add unit tests (mocked) for todos CRUD operations
3. **Phase 3**: Add unit tests (mocked) for projects CRUD operations
4. **Phase 4**: Add unit tests (mocked) for read operations
5. **Phase 5**: Add real integration tests with automatic cleanup for todos
6. **Phase 6**: Add real integration tests with automatic cleanup for projects
7. **Phase 7**: Add error handling tests (mocked)
8. **Phase 8**: Add test commands to pyproject.toml (test, test:dev, test:unit, test:integration)
9. **Phase 9**: Validate coverage and document

No rollback needed - tests are additive and don't affect production code.

## Open Questions

- Should we add optional real integration tests that require Things 3? (Answer: **Yes, included in initial implementation with automatic cleanup**)
- What minimum test coverage should we target? (Answer: >80% on handlers.py)
- Should tests run in CI/CD? (Answer: **Unit tests (mocked) run in CI/CD. Real integration tests are dev-only**)

