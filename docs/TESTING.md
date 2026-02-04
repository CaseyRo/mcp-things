# Testing Guide

This document describes the test suite for the Things MCP server.

## Test Structure

### Layout

| File | Focus | Markers |
|------|--------|---------|
| `tests/conftest.py` | Shared fixtures, mock data, `mcp_server_process`, `mcp_client` | — |
| `tests/mcp_client.py` | Lightweight MCP client for streamable-http tests | — |
| `tests/pytest_test_results.py` | Pytest plugin that writes `test-results/test-results.md` | — |

### Unit tests (no real server or Things 3)

| File | Focus |
|------|--------|
| `test_accept_headers.py` | Accept-header middleware |
| `test_configuration.py` | Settings and validation |
| `test_mcp_protocol.py` | JSON-RPC and protocol shape |
| `test_schema_transforms.py` | Schema transforms (anyOf, etc.) |
| `test_transport_endpoints.py` | Transport endpoint configuration |
| `test_transport_smoke.py` | Transport and lifespan smoke |

### Integration tests (may start server, no Things 3)

| File | Focus |
|------|--------|
| `test_lifespan.py` | Lifespan startup and shutdown |
| `test_mcp_streamable_http.py` | Streamable-http and MCP client |
| `test_server_startup.py` | Server subprocess and `/mcp` endpoint |

### Real integration tests (Things 3 required)

Run only locally or in deployment where Things 3 is available. **Never run in CI** (Things 3 is not available there).

| File | Focus |
|------|--------|
| `test_gtd_workflow.py` | GTD workflows against Things 3 |
| `test_mcp_crud_integration.py` | CRUD via MCP against Things 3 |

## Test Markers

Defined in `pytest.ini`:

- **`unit`** – Fast unit tests with mocked dependencies (CI-safe).
- **`integration`** – Multi-step or server-involved tests (may be mocked).
- **`real`** – Requires Things 3 (local/deployment only; excluded by default).
- **`slow`** – May take longer; exclude with `-m "not slow"`.

**Default run:** `pytest tests` excludes `real` (via `addopts = -m "not real"`), so the default is CI-safe.

## When Tests Run

### Default (CI and pre-commit)

- **`uv run python -m pytest tests`** or **`uv run test`** runs all tests **except** `real`.
- This is the default and is safe for CI and pre-commit (Things 3 is not required).

### Pre-commit hooks

On `git commit`, when relevant files change:

1. **Unit tests** – `pytest tests -m "not real and not integration"` when `tests/**/*.py` or `src/things_mcp/**/*.py` change.
2. **Smoke test** – `scripts/smoke_test.py` when `src/things_mcp/**/*.py` change.  
   The script checks whether Things 3 is available on the host (`is_things_running()`). If not, it exits 0 and skips; the hook does not block the commit.

### CI (GitHub Actions)

- Lint: `ruff check .` and `ruff format --check .`
- Tests: `pytest tests` (same as default; excludes `real`).

### Local / deployment (with Things 3)

- **Real integration tests only:**  
  `uv run python -m pytest tests -m real`
- **All tests including real:**  
  Override the default marker so `real` is not excluded:  
  `uv run python -m pytest tests -o addopts="-v --tb=short --strict-markers --asyncio-mode=auto"`

## Running Tests

### CI-safe (default)

```bash
uv run python -m pytest tests
# or
uv run test
```

### Unit tests only (fastest)

```bash
uv run python -m pytest tests -m "not real and not integration"
```

### Real integration tests only (Things 3 required)

```bash
uv run python -m pytest tests -m real
```

### With coverage

```bash
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing
```

## Test Results History

When the `pytest_test_results` plugin is loaded (via `conftest.py`), test results are written to `test-results/test-results.md` after each run (last 3 runs). This directory is gitignored.

## Smoke Test (Things 3)

For a quick sanity check with Things 3 running:

```bash
uv run python scripts/smoke_test.py
```

The script checks `is_things_running()` first. If Things 3 is not available, it exits 0 and prints a skip message (does not block commits or CI).

## Writing New Tests

### Unit test (CI-safe)

Use `@pytest.mark.unit` and mock external dependencies (things-py, AppleScript, URL scheme). No `real` or `integration` marker.

### Integration test (no Things 3)

Use `@pytest.mark.integration`. May start the server subprocess or use the MCP client against a real server; do not require Things 3.

### Real integration test (Things 3 only)

Use `@pytest.mark.real` and `@pytest.mark.integration`. Require Things 3; use the `test_data_tracker` fixture and `MCP-TEST-`-prefixed data; tests skip if Things 3 is not available.

## Troubleshooting

### Things 3 not available

Real integration tests and the smoke script skip when Things 3 is not running. Start Things 3 and ensure scripting permissions are enabled if you want to run `-m real` or `scripts/smoke_test.py`.

### Test data left in Things 3

Ensure tests use the `test_data_tracker` fixture and the `MCP-TEST-` prefix so cleanup runs. Manually delete any remaining items with that prefix if needed.
