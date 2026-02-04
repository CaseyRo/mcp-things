
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Things MCP is a Model Context Protocol server for Things 3 (macOS task management app). It enables AI assistants to interact with Things 3 through natural language via the FastMCP framework. **macOS only** - requires native AppleScript and URL scheme access.

## Setup

**Prerequisites:** macOS, Things 3 installed with scripting permissions, Python 3.12+, uv package manager

```bash
# Clone and install
git clone https://github.com/CaseyRo/things-fastmcp.git
cd things-fastmcp
uv pip install -e .

# Configure authentication token
python scripts/configure_token.py
```

## Common Commands

```bash
# Run server
uv run server                    # Production mode (binds to 127.0.0.1:8009)
uv run dev                       # Development mode
mcp dev src/things_mcp/things_fast_server.py  # Dev mode with auto-reload

# Lint and format
ruff check .
ruff format .

# Run tests
uv run python -m pytest tests                    # All tests (requires Things 3)
uv run python -m pytest tests -m "not real"      # Unit tests only (CI/CD safe)
uv run python -m pytest tests -m real            # Real integration tests only
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing  # With coverage
```

## Architecture

```
src/things_mcp/
├── fast_server.py           # Entry point: creates MCP server, registers all tools
├── server_core.py           # Server factory, n8n middleware, schema patches
├── client_compat.py         # Client compatibility: Accept header patches, transport middleware
├── tool_annotations.py      # Shared TOOL_ANNOTATIONS dict
├── tools_gtd_core.py        # GTD Engage/Capture/Clarify tools (6 tools)
├── tools_gtd_organize.py    # GTD Organize stage tools (5 tools)
├── tools_gtd_reflect.py     # GTD Reflect stage tools (2 tools)
├── tools_utility.py         # Utility tools: search, list, cache stats (6 tools)
├── url_scheme.py            # Things URL scheme builders + execution (things:///)
├── applescript_bridge.py    # AppleScript execution (run_applescript())
├── formatters.py            # Output formatting for todos/projects/areas
├── cache.py                 # @cached(ttl=seconds) decorator
├── utils.py                 # circuit_breaker, rate_limiter, app_state
├── logging_config.py        # Structured logging with redaction
├── tag_handler.py           # Auto-creates missing tags
└── config.py                # Configuration management
```

**Tool Organization by GTD Stage (19 tools total):**
- **Engage** (3): get-tasks, focus-mode, complete-task
- **Capture** (1): capture-task
- **Clarify** (2): process-inbox, convert-to-project
- **Organize** (5): schedule-task, delegate-task, defer-task, plan-project, modify-task
- **Reflect** (2): daily-review, weekly-review
- **Utility** (6): search-tasks, get-projects, get-areas, get-tags, show-in-app, get-cache-stats

**Data Flow:**
1. Read operations: FastMCP → things-py (SQLite) → cache → format response
2. Write operations: FastMCP → URL scheme builder → macOS `open -g` → Things app

## Key Patterns (FastMCP 3.0)

- **Tool registration**: Use `@mcp.tool(name="kebab-case", annotations=TOOL_ANNOTATIONS["name"])`
- **Async tools**: All tool functions must be `async def` with `ctx: Context` parameter for logging
- **Error handling**: Raise `ToolError("message")` for failures (FastMCP 3 pattern)
- **Context logging**: Use `await ctx.info("message")` for operation logging within tools
- **Tool timeouts**: Write tools use `timeout=30`, read tools use `timeout=5`
- **Caching**: Use `@cached(ttl=CACHE_TTL.get("operation", 30))` for read operations
- **Logging**: Use `get_logger(__name__)`, redact sensitive data (never log task titles/notes)
- **Tags**: Call `ensure_tags_exist(tags)` before using tags in write operations

## Environment Variables

```bash
THINGS_FASTMCP_HOST=127.0.0.1    # Server bind address (default: localhost)
THINGS_FASTMCP_PORT=8009         # Server port
THINGS_MCP_TRANSPORT=streamable-http  # Transport: "streamable-http" (default, SSE removed)
THINGS_AUTH_TOKEN=your-token     # REQUIRED: Get from Things → Settings → General → Enable Things URLs
THINGS_MCP_DEBUG=false           # Enable verbose debug logging to console (default: INFO only)
THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT=1  # Debug: show Things in foreground
```

**Important:** The `THINGS_AUTH_TOKEN` is required for all write operations (create, update, delete). Without it, operations will fail silently. Configure via `.env` file or environment variable.

## OpenSpec Workflow

This project uses OpenSpec for spec-driven development. When planning features or breaking changes:

1. Review `openspec/project.md` for conventions
2. Run `openspec list` to see active changes
3. Run `openspec list --specs` to see existing capabilities
4. Create proposals in `openspec/changes/<change-id>/` with:
   - `proposal.md` - Why and what changes
   - `tasks.md` - Implementation checklist
   - `design.md` - Technical decisions (if needed)
   - `specs/<capability>/spec.md` - Requirement deltas
5. Validate with `openspec validate <change-id> --strict`

**Cursor commands available:**
- `/openspec-proposal` - Create new change proposal
- `/openspec-apply` - Implement approved change
- `/openspec-archive` - Archive completed change

## Testing Notes

- Default run is CI-safe: `pytest tests` excludes `real` (addopts in pytest.ini)
- Markers: `unit`, `integration`, `real`, `slow`; real tests require Things 3 (local/deployment only, never in CI)
- Real tests need Things 3 running + `THINGS_AUTH_TOKEN` in `.env`; test data uses `MCP-TEST-` prefix and auto-cleans
- Results saved to `test-results/test-results.md` (plugin in conftest)
- Main branch is `source` (not `main`)

## Client Compatibility & Endpoints

The server uses streamable-http transport (SSE transport removed as deprecated):

| Endpoint | Transport | Clients | Use Case |
|----------|-----------|---------|----------|
| `/mcp` | Streamable-HTTP | Claude Desktop, n8n, ChatGPT | All MCP clients |

**Transport Configuration:**
```bash
THINGS_MCP_TRANSPORT=streamable-http  # Default: streamable-http transport (only option)
```

**Client Setup:** All clients (ChatGPT, Claude Desktop, n8n) should use `http://localhost:8009/mcp` as the MCP server URL.

## n8n Integration

n8n's MCP Client Tool has a [known bug (#21500)](https://github.com/n8n-io/n8n/issues/21500) where it sends extra parameters (`toolCallId`, `sessionId`, `action`, `chatInput`) that cause Pydantic validation errors. The server includes `ClientCompatibilityMiddleware` that automatically strips these parameters (requires FastMCP 2.9+).

## Important Constraints

- **macOS required**: No Docker support due to AppleScript/URL scheme dependencies
- **Python 3.12+**: Uses modern type hints and f-strings
- **Log redaction**: Never log task titles, notes, or user content
- **Things URL scheme**: Write operations have no direct response; assume success unless app fails
