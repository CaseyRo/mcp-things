## 1. Test Infrastructure Setup

- [x] 1.1 Create `tests/` directory structure
- [x] 1.2 Create `tests/conftest.py` with pytest fixtures for:
  - Mock Things 3 database (things-py library) - for unit tests
  - Mock AppleScript execution - for unit tests
  - Mock URL scheme execution - for unit tests
  - Test data generators
  - Real Things 3 integration test fixtures with automatic cleanup
  - UUID tracking for created items in real tests
- [x] 1.3 Configure pytest markers for test categorization (unit, integration, real, slow)
- [x] 1.4 Add test utilities for common assertions and data validation
- [x] 1.5 Add cleanup fixture that deletes test items after real integration tests

## 2. Create Operation Tests (Unit - Mocked)

- [x] 2.1 Test `add-todo` with minimal required parameters (title only) - mocked
- [x] 2.2 Test `add-todo` with all optional parameters (notes, when, tags, list_title) - mocked
- [x] 2.3 Test `add-todo` error handling (missing title, invalid parameters) - mocked
- [x] 2.4 Test `add-project` with minimal required parameters (title only) - mocked
- [x] 2.5 Test `add-project` with all optional parameters (notes, when, deadline, tags, area_id, todos) - mocked
- [x] 2.6 Test `add-project` error handling (missing title, invalid parameters) - mocked
- [x] 2.7 Verify created items can be retrieved via read operations - mocked

## 2b. Create Operation Tests (Real Integration)

- [x] 2b.1 Test `add-todo` with minimal required parameters (title only) - real Things 3, with cleanup
- [x] 2b.2 Test `add-todo` with all optional parameters (notes, when, tags, list_title) - real Things 3, with cleanup
- [x] 2b.3 Test `add-project` with minimal required parameters (title only) - real Things 3, with cleanup
- [x] 2b.4 Test `add-project` with all optional parameters - real Things 3, with cleanup
- [x] 2b.5 Verify created items are automatically deleted after test completion

## 3. Read Operation Tests (Unit - Mocked)

- [x] 3.1 Test `get-todos` with no filters (returns all todos) - mocked
- [x] 3.2 Test `get-todos` filtered by project_uuid - mocked
- [x] 3.3 Test `get-projects` with include_items=True and False - mocked
- [x] 3.4 Test `get-areas` with include_items=True and False - mocked
- [x] 3.5 Test `get-tags` with include_items=True and False - mocked
- [x] 3.6 Test list view tools: `get-inbox`, `get-today`, `get-upcoming`, `get-anytime`, `get-someday`, `get-logbook`, `get-trash` - mocked
- [x] 3.7 Test `get-tagged-items` with valid tag name - mocked
- [x] 3.8 Test `search-todos` with query string - mocked
- [x] 3.9 Test `search-advanced` with various filter combinations - mocked
- [x] 3.10 Test `get-recent` with different period values - mocked
- [x] 3.11 Verify response formatting matches expected structure - mocked

## 4. Update Operation Tests (Unit - Mocked)

- [x] 4.1 Test `update-todo` with title change - mocked
- [x] 4.2 Test `update-todo` with notes update - mocked
- [x] 4.3 Test `update-todo` with date changes (when, deadline) - mocked
- [x] 4.4 Test `update-todo` with tag updates (add, remove, replace) - mocked
- [x] 4.5 Test `update-todo` with completion status (completed=True) - mocked
- [x] 4.6 Test `update-todo` with cancellation (canceled=True) - mocked
- [x] 4.7 Test `update-todo` error handling (missing id, invalid id) - mocked
- [x] 4.8 Test `update-project` with title change - mocked
- [x] 4.9 Test `update-project` with notes, dates, tags updates - mocked
- [x] 4.10 Test `update-project` with completion/cancellation - mocked
- [x] 4.11 Test `update-project` error handling (missing id, invalid id) - mocked
- [x] 4.12 Verify updated items reflect changes in subsequent read operations - mocked

## 4b. Update Operation Tests (Real Integration)

- [x] 4b.1 Test `update-todo` with title change - real Things 3, with cleanup
- [x] 4b.2 Test `update-todo` with notes, dates, tags updates - real Things 3, with cleanup
- [x] 4b.3 Test `update-todo` with completion status - real Things 3, with cleanup
- [x] 4b.4 Test `update-project` with title and other field updates - real Things 3, with cleanup
- [x] 4b.5 Verify updated items are automatically deleted after test completion

## 5. Integration Tests (Unit - Mocked)

- [x] 5.1 Test complete workflow: create todo → read todo → update todo → verify changes - mocked
- [x] 5.2 Test complete workflow: create project → add todos to project → read project with items → update project - mocked
- [x] 5.3 Test tag workflow: create todo with tags → get-tagged-items → verify tag association - mocked
- [x] 5.4 Test search workflow: create multiple todos → search-todos → verify results - mocked
- [x] 5.5 Test list view workflow: create todo in inbox → get-inbox → verify presence - mocked

## 5b. Integration Tests (Real - Things 3)

- [x] 5b.1 Test complete workflow: create todo → read todo → update todo → verify changes - real Things 3, with cleanup
- [x] 5b.2 Test complete workflow: create project → add todos to project → read project with items → update project - real Things 3, with cleanup
- [x] 5b.3 Test tag workflow: create todo with tags → get-tagged-items → verify tag association - real Things 3, with cleanup
- [x] 5b.4 Test search workflow: create multiple todos → search-todos → verify results - real Things 3, with cleanup
- [x] 5b.5 Verify all test data is automatically cleaned up after integration tests complete

## 6. Error Handling & Edge Cases

- [x] 6.1 Test invalid UUID formats
- [x] 6.2 Test missing required parameters
- [x] 6.3 Test empty string parameters
- [x] 6.4 Test None/null parameter handling
- [x] 6.5 Test very long strings (title, notes)
- [x] 6.6 Test special characters in titles and notes
- [x] 6.7 Test invalid date formats
- [x] 6.8 Test operations when Things app is not available (mocked)
- [x] 6.9 Verify error messages are user-friendly and informative

## 7. Test Commands Setup

- [x] 7.1 Add `test` command to pyproject.toml (runs unit tests only, CI/CD safe)
- [x] 7.2 Add `test-dev` command to pyproject.toml (runs unit + real integration tests)
- [x] 7.3 Add `test-unit` command to pyproject.toml (explicitly runs only unit tests)
- [x] 7.4 Add `test-integration` command to pyproject.toml (runs only real integration tests)
- [x] 7.5 Verify `test` command excludes real integration tests (CI/CD safe)
- [x] 7.6 Verify `test-dev` command includes both unit and real integration tests

## 8. Test Execution & Validation

- [ ] 8.1 Run `pytest` (or `uv run test`) to ensure all unit tests pass
- [ ] 8.2 Run `pytest --cov` to check test coverage (aim for >80% on handlers)
- [ ] 8.3 Run `uv run test:dev` locally to verify real integration tests work
- [ ] 8.4 Verify unit tests run in CI/CD environment (if applicable)
- [ ] 8.5 Verify real integration tests are skipped in CI/CD (Things 3 not available)
- [ ] 8.6 Document test execution commands in README or contributing guide
- [ ] 8.7 Run `ruff check .` to ensure code quality

## 9. Documentation

- [ ] 9.1 Add test documentation to README or create TESTING.md
- [ ] 9.2 Document how to run unit tests (CI/CD safe)
- [ ] 9.3 Document how to run real integration tests locally (requires Things 3)
- [ ] 9.4 Document test structure and organization
- [ ] 9.5 Document automatic cleanup behavior for real integration tests
- [ ] 9.6 Update AGENTS.md log with test addition
