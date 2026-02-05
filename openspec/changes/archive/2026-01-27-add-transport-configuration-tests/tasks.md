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

## 6. Transport Smoke Tests

- [x] 6.1 Create `tests/test_transport_smoke.py` with fast smoke tests
- [x] 6.2 Add test for both transports configured simultaneously
- [x] 6.3 Add test for SSE transport configured independently
- [x] 6.4 Add test for streamable-http transport configured independently
- [x] 6.5 Add test for app lifespan configuration
- [x] 6.6 Add test for all transport modes creating valid apps
- [x] 6.7 Verify tests use proper pytest markers (`@pytest.mark.unit`)
- [x] 6.8 Verify tests run fast enough for pre-commit (< 15 seconds)

## 7. Pre-commit Hook Integration

- [x] 7.1 Update `.pre-commit-config.yaml` to add unit test hook
- [x] 7.2 Configure hook to run `pytest -m "not real and not integration"`
- [x] 7.3 Set hook to trigger on test and source file changes
- [x] 7.4 Add transport smoke test hook for transport-specific file changes
- [x] 7.5 Configure transport hook to run transport smoke, endpoint, accept header, and configuration tests
- [x] 7.6 Verify hooks run fast enough for pre-commit (< 15 seconds each)
- [x] 7.7 Test hook execution manually
- [x] 7.8 Verify hooks trigger correctly on file changes

## 8. Server Verification

- [x] 8.1 Verify server starts successfully with both transports enabled
- [x] 8.2 Verify server logs show successful startup for both transports
- [x] 8.3 Verify server shutdown completes gracefully
- [x] 8.4 Confirm both `/sse/` and `/mcp` endpoints are configured correctly
- [x] 8.5 Verify lifespan management prevents "Task group is not initialized" errors

## 9. Test Execution & Validation

- [x] 9.1 Run all new unit tests to verify they pass (19 transport tests + 26 unit tests = 45 total)
- [x] 9.2 Run all new integration tests to verify they pass
- [x] 9.3 Verify test markers work correctly (can exclude real/integration tests)
- [x] 9.4 Verify pre-commit hooks execute tests correctly
- [x] 9.5 Verify transport smoke test hook runs when transport files change
- [x] 9.6 Run `ruff check` to ensure code quality

## 10. Documentation

- [x] 10.1 Add test file docstrings explaining test purpose
- [x] 10.2 Document test markers in test files
- [x] 10.3 Verify tests follow existing test patterns
- [x] 10.4 Document pre-commit hook configuration and execution
