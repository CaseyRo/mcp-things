# Developer Guide

This guide covers development setup, architecture, testing, and contributing to the Things 3 GTD MCP Server.

## GTD Context for Developers

Understanding GTD (Getting Things Done) helps you contribute effectively. The codebase is organized around GTD's five stages:

| Stage | Purpose | Tools |
|-------|---------|-------|
| **Capture** | Get things out of your head quickly | `capture-task` |
| **Clarify** | Decide what each item means and what to do | `process-inbox`, `convert-to-project` |
| **Organize** | Put items where they belong | `schedule-task`, `delegate-task`, `defer-task`, `plan-project` |
| **Reflect** | Review your system regularly | `daily-review`, `weekly-review` |
| **Engage** | Do the work | `get-tasks`, `focus-mode`, `complete-task` |

When adding or modifying tools, consider which GTD stage they support and ensure tool descriptions help AI assistants route user requests appropriately.

## FastMCP 3.0

This project uses **FastMCP 3.0**, the modern async-first MCP framework. Key patterns:

### Tool Registration

```python
@mcp.tool(name="kebab-case-name", annotations=TOOL_ANNOTATIONS["name"], timeout=5)
async def tool_name(
    param: str,
    optional_param: Optional[str] = None,
    ctx: Context = None,  # Required for logging
) -> str:
    """Tool description for AI assistants.

    GTD Stage: [Capture|Clarify|Organize|Reflect|Engage]
    Use when: [specific user intents this tool handles]
    Instead use: [alternative tool] if [different situation]
    """
    await ctx.info("Starting operation")
    # ... implementation
    return "Result for AI assistant"
```

### Error Handling

```python
from mcp.server.fastmcp import ToolError

# Raise ToolError for operation failures
raise ToolError("Task not found. Use get-tasks to find available tasks.")
```

### Caching

```python
from things_mcp.cache import cached, CACHE_TTL

@cached(ttl=CACHE_TTL.get("inbox", 30))
def get_cached_data():
    # Cached for 30 seconds
    pass
```

### Tool Annotations

Define read-only, idempotent, and destructive hints in `TOOL_ANNOTATIONS`:

```python
TOOL_ANNOTATIONS = {
    "get-tasks": ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    "complete-task": ToolAnnotations(readOnlyHint=False, idempotentHint=False),
}
```

## Development Setup

### Prerequisites

- macOS (required for AppleScript and URL schemes)
- Things 3 installed with scripting permissions
- Python 3.12+
- uv package manager

### Installation

```bash
git clone https://github.com/CaseyRo/things-fastmcp.git
cd things-fastmcp
uv pip install -e .

# Configure authentication token
python scripts/configure_token.py
```

### Environment Variables

Create a `.env` file:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `THINGS_FASTMCP_HOST` | `127.0.0.1` | Server bind address |
| `THINGS_FASTMCP_PORT` | `8009` | Server port |
| `THINGS_MCP_TRANSPORT` | `streamable-http` | Transport protocol (streamable-http only) |
| `THINGS_AUTH_TOKEN` | (required) | Things URL scheme auth token |
| `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` | unset | Show Things in foreground for debugging |

**Transport Configuration:**

- The server uses **streamable-http transport only** (SSE transport removed as deprecated)
- Endpoint: `/mcp` (streamable-http transport)
- Compatible with: Claude Desktop, n8n MCP Client Tool node, ChatGPT (via streamable-http)

### Running the Server

```bash
# Production mode
uv run server

# Development mode with auto-reload
uv run dev

# Alternative: MCP CLI development helper
mcp dev src/things_mcp/things_fast_server.py
```

## Architecture

### Data Flow

```
Read Operations:
  MCP Client → FastMCP → things-py (SQLite) → cache → format → response

Write Operations:
  MCP Client → FastMCP → URL scheme builder → macOS `open -g` → Things app
```

### Source Structure

```
src/things_mcp/
├── fast_server.py        # FastMCP server, tool definitions, INSTRUCTIONS_TEXT
├── url_scheme.py         # Things URL scheme builders + execution
├── applescript_bridge.py # run_applescript() for AppleScript execution
├── formatters.py         # format_todo(), format_project(), format_area()
├── cache.py              # @cached(ttl=seconds) decorator
├── utils.py              # circuit_breaker, rate_limiter, app_state
├── logging_config.py     # get_logger(), redaction for privacy
├── tag_handler.py        # ensure_tags_exist() auto-creates tags
└── config.py             # Configuration management
```

### Key Modules

**fast_server.py** — Main entry point with all tool definitions. Tools are organized by GTD stage in the source code.

**url_scheme.py** — Builds Things URL scheme URLs for write operations. Key functions:

- `add_todo()`, `update_todo()` — Task operations
- `add_project()`, `update_project()` — Project operations
- `add_project_with_tasks()` — Atomic project creation via JSON API
- `append_notes()`, `prepend_notes()`, `add_tags()` — Incremental updates

**formatters.py** — Formats Things data for AI-readable responses. Returns structured text, not JSON.

**cache.py** — TTL-based caching for read operations. Cache invalidation happens on write operations.

### Things 3 Integration

**Read operations** use [things-py](https://github.com/thingsapi/things.py), which reads directly from Things 3's SQLite database.

**Write operations** use the [Things URL scheme](https://culturedcode.com/things/support/articles/2803573/), executed via `open -g "things:///..."`. The `-g` flag runs in background.

## Testing

### Test Structure

See **[docs/TESTING.md](TESTING.md)** for full details. Summary:

- **Unit** (no server/Things 3): `test_accept_headers`, `test_configuration`, `test_mcp_protocol`, `test_schema_transforms`, `test_transport_*`
- **Integration** (may start server, no Things 3): `test_lifespan`, `test_mcp_streamable_http`, `test_server_startup`
- **Real** (Things 3 required, local/deployment only): `test_gtd_workflow`, `test_mcp_crud_integration`
- `conftest.py`: fixtures, mock generators, `pytest_plugins = ["pytest_test_results"]`
- `pytest_test_results.py`: plugin that writes `test-results/test-results.md`

### Running Tests

Default run is **CI-safe** (excludes `real` via pytest.ini addopts):

```bash
# CI-safe (default; no Things 3 needed)
uv run python -m pytest tests

# Real integration tests only (Things 3 required)
uv run python -m pytest tests -m real

# With coverage
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing
```

### Test Markers

| Marker | Purpose |
|--------|---------|
| `unit` | Unit tests with mocked dependencies (CI-safe) |
| `integration` | Integration tests (may use mocks or real server) |
| `real` | Real integration tests requiring Things 3 (excluded by default) |
| `slow` | Tests that take longer |

### Test Data

- Real tests use `MCP-TEST-` prefix and auto-clean via `test_data_tracker`
- Results saved to `test-results/test-results.md` when the results plugin is loaded

### Writing Tests

GTD workflow tests follow this pattern:

```python
@pytest.mark.real
@pytest.mark.integration
class TestGTDCapture:
    @pytest.mark.asyncio
    async def test_capture_task_to_inbox(self, test_data_tracker):
        """Capture should create task in Inbox."""
        title = generate_test_title("GTD-CAPTURE")

        result = await capture_task(title=title, notes="Test note")

        assert "Captured" in result
        # Track for cleanup
        todo = find_todo_by_title(title)
        if todo:
            test_data_tracker.add_todo(todo["uuid"])
```

## Code Quality

### Linting and Formatting

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`):

- `ruff` — Linting
- `ruff-format` — Formatting
- Smoke test — Verifies Things 3 integration

Install hooks:

```bash
uv pip install pre-commit
pre-commit install
```

### Logging Guidelines

- Use `get_logger(__name__)` for module loggers
- Never log task titles, notes, or user content (privacy)
- Use `await ctx.info()` inside tools for operation logging

```python
from things_mcp.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Starting operation", extra={"task_count": len(tasks)})
```

## OpenSpec Workflow

This project uses **OpenSpec** for spec-driven development of significant changes.

### When to Use OpenSpec

- New features or capabilities
- Breaking changes to existing tools
- Architecture changes
- Performance or security work

### Creating a Change Proposal

```bash
# List active changes
openspec list

# Create new change
mkdir -p openspec/changes/<change-id>
```

Required files:

- `proposal.md` — Why and what changes
- `tasks.md` — Implementation checklist
- `design.md` — Technical decisions (if needed)
- `specs/<capability>/spec.md` — Requirement deltas

### Validating Changes

```bash
openspec validate <change-id> --strict
```

See `openspec/AGENTS.md` for detailed instructions.

## Contributing

1. **Check existing issues** and OpenSpec proposals
2. **Create an OpenSpec proposal** for significant changes
3. **Follow GTD stage organization** when adding tools
4. **Write tests** for new functionality
5. **Run linting and tests** before submitting PRs:

   ```bash
   uv run ruff check . && uv run ruff format .
   uv run python -m pytest tests -v
   ```

### Pull Request Guidelines

- Reference related issues or OpenSpec proposals
- Include test coverage for new functionality
- Ensure all pre-commit hooks pass
- Update tool documentation if adding/modifying tools

## Troubleshooting

### Server Won't Start

- Verify Things 3 is installed and running
- Check Python version: `python --version` (requires 3.12+)
- Review logs for "Things app not available" messages

### Operations Failing

- Check circuit breaker status in logs
- Review Dead Letter Queue: `cat things_dlq.json`
- Verify Things has automation permissions (System Settings → Privacy & Security)

### Performance Issues

- Check cache hit rate: Use `get-cache-stats` tool
- Review rate limiter logs for throttling
- Increase cache TTL for slower-changing data

### Debug Mode

```bash
# Show Things in foreground during operations
export THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT=1

# Enable debug logging (edit logging_config.py)
# Set console_level="DEBUG"
```

## Resources

- [FastMCP Documentation](https://gofastmcp.com)
- [MCP Specification](https://github.com/anthropics/mcp)
- [Things 3 URL Scheme](https://culturedcode.com/things/support/articles/2803573/)
- [things-py Library](https://github.com/thingsapi/things.py)
- [GTD Methodology](https://gettingthingsdone.com/)
