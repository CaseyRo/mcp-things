# Project Context

## Purpose

This project provides a **Model Context Protocol (MCP) server** for the [Things 3](https://culturedcode.com/things/) task management application on macOS. It enables AI assistants (like Claude Desktop) and automation platforms to interact with Things 3 through natural language and programmatic APIs.

**Goals:**

- Enable natural language task creation and management through AI assistants
- Provide comprehensive access to Things 3 data (tasks, projects, areas, tags)
- Deliver reliable, production-ready MCP integration with caching and error handling
- Maintain privacy and security by operating entirely locally on macOS
- Support both modern FastMCP and legacy MCP implementations during transition

## Tech Stack

### Core Technologies

- **Python 3.12+** - Primary language (requires `>=3.12` per pyproject.toml)
- **FastMCP** - Modern MCP server framework from Anthropic's `mcp` library
- **things-py** - Official Things 3 Python library for database queries
- **Rich** - Terminal UI and colorful logging
- **httpx** - HTTP client for async operations
- **uv** - Fast Python package installer and virtual environment manager

### Build & Tooling

- **Ruff** - Fast Python linter and formatter (replaces Black, flake8, isort)
- **pytest** - Testing framework with coverage support
- **Hatchling** - Modern build backend for packaging
- **Twine** - PyPI package publishing

### Platform Requirements

- **macOS only** - Requires native AppleScript and `open` command access
- **Things 3 app** - Must be installed and have scripting permissions enabled

## Project Conventions

### Code Style

**Linting & Formatting:**

- Use **Ruff** for all linting and formatting (`ruff check .` and `ruff format .`)
- Run `ruff check .` and `pytest` after modifications (per AGENTS.md)
- Follow PEP 8 naming conventions (snake_case for functions/variables, PascalCase for classes)

**Type Hints:**

- Use type hints extensively (see `handlers.py`, `fast_server.py`)
- Common patterns: `Optional[str]`, `List[str]`, `Dict[str, Any]`, `Union[str, types.CallToolResult]`
- Use `from typing import` for type annotations

**Logging:**

- Use structured logging via `logging_config.py`
- Log levels: INFO for operations, DEBUG for URLs/details, WARNING for retries, ERROR for failures
- **Redact sensitive data** - Never log task titles, notes, or user content (see `_summarize_parameters()` in handlers.py)
- Use `get_logger(__name__)` pattern in all modules

**Docstrings:**

- Use triple-quoted docstrings for all public functions/tools
- Include Args section with parameter descriptions
- FastMCP tools display docstrings to users - keep them clear and helpful

### Architecture Patterns

**Modular Design:**

```
src/things_mcp/
├── fast_server.py       # FastMCP implementation (primary)
├── handlers.py          # Tool handler functions with reliability features
├── url_scheme.py        # Things URL scheme builders
├── applescript_bridge.py # AppleScript execution layer
├── formatters.py        # Output formatting for todos/projects/areas
├── cache.py             # Caching decorator and utilities
├── utils.py             # Reliability features (circuit breaker, DLQ, rate limiter)
├── logging_config.py    # Structured logging setup
├── tag_handler.py       # Tag creation and management
└── config.py            # Configuration management
```

**Key Patterns:**

1. **Decorator-based tool registration** - Use `@mcp.tool()` with annotations for FastMCP
2. **Error handling** - Return `_error_result()` for failures (standardized MCP error response)
3. **Caching** - Use `@cached(ttl=seconds)` decorator for read operations
4. **Circuit breaker** - Automatic failure protection via `circuit_breaker.allow_operation()`
5. **Rate limiting** - Prevent API abuse via `rate_limiter.check_rate_limit()`
6. **Dead letter queue** - Track failed operations in `things_dlq.json`
7. **Retry logic** - Exponential backoff with jitter in `retry_operation()`
8. **Privacy-first** - Redact sensitive data in logs, summarize params instead of logging raw content

**MCP Tool Annotations:**

- `READ_ONLY_ANNOTATIONS` - For queries (readOnlyHint=True, idempotentHint=True)
- `ADD_ANNOTATIONS` - For creation operations (destructiveHint=False, idempotentHint=False)
- `UPDATE_ANNOTATIONS` - For updates (idempotentHint=True since same params → same result)

**Configuration:**

- Environment variables: `THINGS_MCP_HOST` (default: `127.0.0.1`) and `THINGS_MCP_PORT` (default: `8009`)
- Use `@lru_cache(maxsize=1)` for config getters (`get_binding_host()`, `get_binding_port()`)
- Validate and fall back to defaults for invalid env var values

### Testing Strategy

**Framework:**

- Use `pytest` with coverage reporting (`pytest-cov`)
- Run tests via `pytest {args:tests}` (configured in pyproject.toml)

**Requirements:**

- Run `pytest` after modifications (per AGENTS.md workflow)
- Test coverage for new features
- Mock Things 3 interactions for unit tests

**Test Organization:**

- Place tests in `tests/` directory (not shown in current tree but implied by pytest.ini)
- Use fixtures for common setup
- Test both success and failure paths

### Git Workflow

**Branching:**

- Main branch: `source` (per git status)
- Development happens on feature branches
- Merge to `source` after testing

**Commit Conventions:**

- Record significant changes in `AGENTS.md` under `## Log` with date stamps
- Use clear, descriptive commit messages
- Reference change proposals for major features (per OpenSpec workflow)

**Quality Gates:**

- Run `ruff check .` before committing
- Run `pytest` to ensure tests pass
- Update CHANGELOG.md for user-facing changes

## Domain Context

### Things 3 Integration

**Data Model:**

- **Todos** - Individual tasks with title, notes, dates, tags, checklists
- **Projects** - Collections of todos with their own metadata
- **Areas** - High-level groupings for projects and todos (e.g., "Work", "Personal")
- **Tags** - Cross-cutting labels that can be applied to any item
- **Lists** - Built-in views (Inbox, Today, Upcoming, Anytime, Someday, Logbook, Trash)

**Access Methods:**

1. **things-py library** - Direct SQLite database reads for queries (fast, read-only)
2. **Things URL Scheme** - Write operations via `things:///` URLs opened with macOS `open` command
3. **AppleScript bridge** - Fallback for operations that require app interaction

**URL Scheme Format:**

```
things:///add?title=Task&notes=Description&when=today&tags=tag1,tag2
things:///update?id=UUID&title=New+Title&completed=true
things:///show?id=today&query=search
```

### MCP Protocol

**Model Context Protocol** - Standard for AI assistants to access local tools and data:

- Tools are exposed with names (kebab-case), descriptions, and JSON schemas
- Clients (Claude Desktop, n8n) discover and invoke tools
- Servers return structured responses (`TextContent` for success, `isError=True` for failures)
- Metadata (instructions, website, icons) help users understand capabilities

**FastMCP Features:**

- HTTP transport via "streamable-http"
- Automatic JSON schema generation from type hints
- Tool annotations for optimization hints (read-only, idempotent, destructive)
- Backward compatibility checks for newer metadata fields

### macOS-Specific Behavior

**AppleScript:**

- Used for checking app state and launching Things
- Executed via `osascript` subprocess
- Requires "Automation" permissions in System Preferences

**URL Opening:**

- `open` command triggers Things URL scheme handlers
- Things must be running for URLs to succeed
- No feedback mechanism - assume success unless app fails to launch

**No Docker Support:**

- Docker on macOS uses a VM that lacks host-level scripting access
- AppleScript and `open` only work on native macOS
- Server must run directly on macOS host

## Important Constraints

### Technical Constraints

1. **macOS Only** - Absolutely requires macOS for AppleScript and URL scheme access
2. **Python 3.12+** - Project requires modern Python (f-strings, type hints, walrus operator)
3. **Things 3 Required** - App must be installed and have scripting permissions enabled
4. **Local Operation** - All data access is local; no cloud API available
5. **No Attachment Access** - things-py cannot retrieve file attachments from Things database
6. **URL Scheme Limitations** - Some operations take seconds; no direct response from Things

### Performance Constraints

- **Caching TTL** - Configurable per operation in `CACHE_TTL` dict (default: 30-300 seconds)
- **Rate Limiting** - Prevents abuse but may delay rapid operations
- **Circuit Breaker** - Opens after repeated failures, blocking operations temporarily
- **Database Locks** - things-py reads can conflict with Things app writes

### Security & Privacy

1. **User Consent Required** - Privacy Notice and Terms of Use must be reviewed before setup
2. **Local Data Only** - Never transmit task data externally
3. **Log Redaction** - Sensitive content (titles, notes) must not appear in logs
4. **Token-Based Auth** - Things authentication token must be configured via `scripts/configure_token.py`

### Version History

- **v2.0.0 (2025-10-16)** - Removed legacy MCP implementation, consolidated to FastMCP-only
- **v1.0.0 (2025-05-30)** - Initial FastMCP implementation with reliability features

## External Dependencies

### Required Services

1. **Things 3 for macOS** - Commercial task management app by Cultured Code
   - URL: <https://culturedcode.com/things/>
   - Provides SQLite database and URL scheme API
   - Requires purchase and installation

### Python Libraries

- **mcp[cli]** `>=1.2.0` - Anthropic's Model Context Protocol implementation
  - Provides FastMCP framework and MCP development tools
  - CLI tools: `mcp dev` for auto-reload during development

- **things-py** `>=0.0.15` - Official Things 3 Python library
  - SQLite database access layer for read operations
  - Maintained by Cultured Code

- **httpx** `>=0.28.1` - Modern async HTTP client
  - Used for HTTP transport in MCP server

- **rich** `>=13.7.0` - Terminal formatting and logging
  - Colorful output in `run_things_fastmcp.sh`
  - Progress indicators and tables

### Development Tools

- **uv** - Fast package installer (optional but recommended)
  - Bootstrapped by `run_things_fastmcp.sh` if available
  - Falls back to system Python if unavailable

- **ruff** `>=0.1.0` - Python linter and formatter
  - Replaces Black, flake8, isort with single fast tool

- **pytest** `>=7.0.0` - Testing framework
  - With pytest-cov for coverage reports

### External Documentation

- **MCP Specification**: <https://github.com/anthropics/mcp>
- **Things URL Scheme**: <https://culturedcode.com/things/support/articles/2803573/>
- **OpenSpec**: Change proposal workflow (see `openspec/AGENTS.md`)
- **Project Issues**: <https://github.com/CaseyRo/mcp-things/issues>
