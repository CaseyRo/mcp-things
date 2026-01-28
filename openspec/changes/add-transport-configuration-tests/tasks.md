## 1. Transport Endpoint Tests
- [x] 1.1 Create `tests/test_transport_endpoints.py` with tests for SSE endpoint creation
- [x] 1.2 Add tests for streamable-http endpoint creation
- [x] 1.3 Add tests for "both" transport mode (both endpoints exist)
- [x] 1.4 Add tests for single transport mode (other endpoint excluded)
- [x] 1.5 Verify tests use proper pytest markers (`@pytest.mark.unit`)

## 2. Lifespan Management Tests
- [x] 2.1 Create `tests/test_lifespan.py` with tests for dual transport lifespan
- [x] 2.2 Add test for lifespan startup completion
- [x] 2.3 Add test for graceful shutdown
- [x] 2.4 Add tests for independent transport lifespans (SSE only, streamable-http only)
- [x] 2.5 Verify tests use proper pytest markers (`@pytest.mark.integration`)

## 3. Accept Header Compatibility Tests
- [x] 3.1 Create `tests/test_accept_headers.py` with tests for Accept header patching
- [x] 3.2 Add test for patch application success
- [x] 3.3 Add test for middleware wildcard header rewriting
- [x] 3.4 Add test for middleware adding missing Accept headers
- [x] 3.5 Add test for middleware preserving explicit valid headers
- [x] 3.6 Verify tests use proper pytest markers (`@pytest.mark.unit`)

## 4. Configuration Validation Tests
- [x] 4.1 Create `tests/test_configuration.py` with tests for settings validation
- [x] 4.2 Add test for default settings
- [x] 4.3 Add test for transport mode validation
- [x] 4.4 Add test for port validation (range checking)
- [x] 4.5 Add test for host validation
- [x] 4.6 Add test for auth token property
- [x] 4.7 Add test for retry configuration validation
- [x] 4.8 Verify tests use proper pytest markers (`@pytest.mark.unit`)

## 5. Server Startup Smoke Tests
- [x] 5.1 Create `tests/test_server_startup.py` with smoke tests
- [x] 5.2 Add test for server process startup
- [x] 5.3 Add test for SSE endpoint availability
- [x] 5.4 Add test for streamable-http endpoint availability
- [x] 5.5 Mark tests as `@pytest.mark.slow` and `@pytest.mark.integration`
- [x] 5.6 Add graceful skipping when server not accessible

## 6. Pre-commit Hook Integration
- [x] 6.1 Update `.pre-commit-config.yaml` to add unit test hook
- [x] 6.2 Configure hook to run `pytest -m "not real and not integration"`
- [x] 6.3 Set hook to trigger on test and source file changes
- [x] 6.4 Verify hook runs fast enough for pre-commit (< 15 seconds)
- [x] 6.5 Test hook execution manually

## 7. Test Execution & Validation
- [x] 7.1 Run all new unit tests to verify they pass
- [x] 7.2 Run all new integration tests to verify they pass
- [x] 7.3 Verify test markers work correctly (can exclude real/integration tests)
- [x] 7.4 Verify pre-commit hook executes tests correctly
- [x] 7.5 Run `ruff check` to ensure code quality

## 8. Documentation
- [x] 8.1 Add test file docstrings explaining test purpose
- [x] 8.2 Document test markers in test files
- [x] 8.3 Verify tests follow existing test patterns
