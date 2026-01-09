# Things 3 Enhanced MCP Server

A production-ready **Model Context Protocol (MCP) server** for [Things 3](https://culturedcode.com/things/), enabling AI assistants and automation platforms to interact with your task management system through natural language.

> **⚠️ Important:** Review the [Privacy Notice](PRIVACY.md) and [Terms of Use](TERMS_OF_USE.md) before installation.

## Overview

This MCP server provides seamless integration between Things 3 and AI assistants like Claude Desktop, allowing you to manage tasks, projects, and areas using natural language. Built with the modern **FastMCP** framework, it includes production-ready reliability features like intelligent caching, rate limiting, circuit breakers, and comprehensive error handling.

### Key Benefits

- **🗣️ Natural Language Interface**: Create and manage tasks conversationally through AI assistants
- **📊 Smart Insights**: Analyze productivity patterns and project status with AI-powered queries
- **⚡ Production-Ready**: Built-in caching, rate limiting, and automatic retry logic
- **🔒 Privacy-First**: All operations are local-only; your task data never leaves your Mac
- **🔄 Seamless Integration**: Works directly with your existing Things 3 database

## Prerequisites

- **macOS** (required - uses AppleScript and macOS `open` command)
- **Things 3** for macOS with scripting permissions enabled
- **Python 3.12+**
- **uv** package manager (recommended) or standard Python tooling

> **Note:** Docker is not supported due to macOS VM limitations preventing access to host-level AppleScript and URL scheme handlers.

## Features

### 📋 Things 3 Integration

- **List Access**: Inbox, Today, Upcoming, Anytime, Someday, Logbook, and Trash
- **Task Management**: Create, update, search, and organize todos with full metadata
- **Project & Area Management**: Organize tasks into projects and areas with nesting support
- **Tag Operations**: Create, assign, and filter by tags (auto-creates missing tags)
- **Checklist Support**: Include checklist items in task creation
- **Advanced Search**: Filter by status, dates, tags, areas, and custom queries

### 🚀 Reliability Features

- **Intelligent Caching**: Configurable TTL-based caching for read operations
- **Circuit Breaker**: Automatic failure detection and recovery
- **Rate Limiting**: Prevents API abuse and throttles operations safely
- **Dead Letter Queue**: Tracks failed operations for debugging (`things_dlq.json`)
- **Retry Logic**: Exponential backoff with jitter for transient failures
- **Structured Logging**: Privacy-aware logging with sensitive data redaction

### 🔌 MCP Integration

- **FastMCP Framework**: Modern, type-safe MCP implementation
- **Rich Metadata**: Assistants receive instructions, capabilities, and limitations
- **HTTP Transport**: RESTful interface on `http://127.0.0.1:8009` (configurable)
- **Tool Annotations**: Optimization hints for read-only, idempotent, and destructive operations

## Quick Start

### Installation

1. **Review Privacy & Terms**
   Confirm you've read the [Privacy Notice](PRIVACY.md) and [Terms of Use](TERMS_OF_USE.md).

2. **Install uv** (recommended)

   ```bash
   pipx install uv
   # or: pip install uv
   ```

3. **Clone and Install**

   ```bash
   git clone https://github.com/CaseyRo/things-fastmcp.git
   cd things-fastmcp
   uv pip install -e .
   ```

   *The helper script will bootstrap a virtual environment automatically if you skip this step.*

4. **Configure Authentication**

   ```bash
   python configure_token.py
   ```

   Follow the prompts to set up your Things 3 authentication token.

### Running the Server

**Option 1: Production Mode** (recommended)

```bash
uv run server
```

- Binds to `http://127.0.0.1:8009` by default (localhost-only)
- Uses [Rich](https://github.com/Textualize/rich) for colorful terminal output
- Auto-manages virtual environment and dependencies

**Option 2: Development Mode**

```bash
uv run dev
```

Same as production mode but with development-friendly settings.

**Option 3: Manual Development Mode** (with auto-reload)

```bash
mcp dev src/things_mcp/things_fast_server.py
```

Uses the [MCP development helper](https://github.com/anthropics/mcp-cli#development-helper) for automatic reloading on file changes.

### Configuration

**Environment Variables:**

```bash
# Bind to all interfaces (⚠️ exposes server to network)
export THINGS_FASTMCP_HOST=0.0.0.0

# Use custom port
export THINGS_FASTMCP_PORT=9000

# Disable background execution for AppleScript (useful for debugging)
# When set, Things 3 will appear in foreground during operations
export THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT=1
```

**Using .env File:**

Create a `.env` file in the project root for easy configuration:

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your preferred settings
THINGS_FASTMCP_HOST=127.0.0.1
THINGS_FASTMCP_PORT=8009
# THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT=1  # Uncomment to disable background execution
```

**Environment Variable Override:**

```bash
# Override configuration when running
THINGS_FASTMCP_HOST=0.0.0.0 THINGS_FASTMCP_PORT=9000 uv run server
```

## Available MCP Tools

The server exposes 19 tools organized into logical groups:

### 📥 List Views

- `get-inbox` - Retrieve items in Inbox
- `get-today` - Get tasks due today
- `get-upcoming` - View upcoming scheduled tasks
- `get-anytime` - List Anytime tasks
- `get-someday` - List Someday/Maybe items
- `get-logbook` - Access completed items (configurable period)
- `get-trash` - View deleted items

### 📝 Task Operations

- `get-todos` - List all todos (optionally filtered by project)
- `add-todo` - Create new tasks with full metadata
- `update-todo` - Modify existing tasks

### 📁 Project & Area Management

- `get-projects` - List all projects
- `get-areas` - List all areas
- `add-project` - Create new projects
- `update-project` - Modify existing projects

### 🏷️ Tag Operations

- `get-tags` - List all tags
- `get-tagged-items` - Filter items by tag

### 🔍 Search & Discovery

- `search-todos` - Search by title or notes
- `search-advanced` - Multi-criteria filtering
- `search-items` - Open search in Things app
- `show-item` - Display specific item or list in Things

### 📊 Diagnostics

- `get-recent` - Recently created items
- `get-cache-stats` - Cache performance metrics

Each tool includes detailed docstrings visible to AI assistants, with parameter descriptions and usage examples.

## Architecture

```text
src/things_mcp/
├── fast_server.py           # FastMCP server with tool definitions
├── handlers.py              # Tool handlers with reliability features
├── url_scheme.py            # Things URL scheme builders
├── applescript_bridge.py    # AppleScript execution layer
├── formatters.py            # Output formatting
├── cache.py                 # Caching decorator (@cached)
├── utils.py                 # Circuit breaker, rate limiter, DLQ
├── logging_config.py        # Structured logging with redaction
└── tag_handler.py           # Automatic tag creation
```

**Data Flow:**

1. MCP client → FastMCP server receives tool call
2. Tool handler validates params and checks circuit breaker
3. Read operations → things-py (SQLite) → cache → format response
4. Write operations → URL scheme builder → macOS `open` command → Things app
5. Errors → retry logic → circuit breaker → dead letter queue if needed

## Usage with AI Assistants

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "things": {
      "command": "uv run server"
    }
  }
}
```

### MCP Client Metadata

AI assistants automatically receive:

- **Instructions**: Available tools, limitations, and privacy reminders
- **Website**: Link to this repository for documentation
- **Icon**: OpenMoji notepad icon for easy recognition

## Development

### Running in Development Mode

```bash
mcp dev things_fast_server.py
```

Enables auto-reload on file changes using the [MCP CLI development helper](https://github.com/anthropics/mcp-cli#development-helper).

### Code Quality

Before committing changes:

```bash
# Lint and format
ruff check .
ruff format .

# Run all tests including real Things 3 integration (requires Things 3)
# Note: 'uv run test' may suppress output; use direct command for visible output
uv run python -m pytest tests

# Run only unit tests (CI/CD safe, excludes real integration tests)
uv run python -m pytest tests -m "not real"

# Check test coverage
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing
```

### Testing

The project includes a comprehensive test suite with both unit tests (mocked, CI/CD safe) and real integration tests (requires Things 3).

**Prerequisites for Real Integration Tests:**

1. Things 3 must be running
2. Authentication token must be configured in `.env`:
   ```bash
   # Copy .env.example and add your token
   cp .env.example .env
   # Edit .env and set THINGS_AUTH_TOKEN
   # Get token from: Things → Settings → General → Enable Things URLs
   ```

**Quick Start:**

```bash
# Run all tests (requires Things 3 + auth token)
uv run python -m pytest tests -v

# Run only unit tests (CI/CD safe, no Things 3 needed)
uv run python -m pytest tests -m "not real"

# Run only real integration tests
uv run python -m pytest tests -m real -v

# Run with coverage report
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing
```

**Test Structure:**
- `tests/test_mcp_workflow.py` - Full MCP workflow tests (create, edit, move, delete)
- `tests/conftest.py` - Fixtures, mock generators, and test utilities
- `tests/pytest_test_results.py` - Test results plugin (saves to markdown)

**Test Markers:**
- `@pytest.mark.unit` - Unit tests with mocked dependencies
- `@pytest.mark.integration` - Integration tests (may use mocks or real Things)
- `@pytest.mark.real` - Real integration tests requiring Things 3
- `@pytest.mark.slow` - Tests that may take longer to run

**Test Results:**
Test results are automatically saved to `test-results/test-results.md` after each run, maintaining a history of the last 3 runs with summaries, failed tests, and breakdowns by marker.

Real integration tests automatically clean up test data after completion (todos/projects prefixed with `MCP-TEST-`).

### Project Conventions

See [openspec/project.md](openspec/project.md) for:

- Code style guidelines
- Architecture patterns
- Type hints conventions
- Logging best practices
- Testing requirements

## Troubleshooting

### Common Issues

**Server won't start:**

- Verify Things 3 is installed and running
- Check Python version: `python --version` (requires 3.12+)
- Review logs for "Things app not available" messages

**Operations failing:**

- Check circuit breaker status in logs
- Review Dead Letter Queue: `cat things_dlq.json`
- Verify Things has automation permissions (System Preferences → Security & Privacy)

**Performance issues:**

- Check cache hit rate: Use `get-cache-stats` tool
- Review rate limiter logs for throttling
- Increase cache TTL in `cache.py` for slower-changing data

### Advanced Debugging

1. **Enable Debug Logging**
   Edit `src/things_mcp/logging_config.py` and set `console_level="DEBUG"`

2. **Monitor Dead Letter Queue**
   Failed operations are logged to `things_dlq.json` with full context

3. **Check Circuit Breaker State**
   Look for "Circuit breaker is open" messages in logs

4. **Cache Performance**
   Use the `get-cache-stats` MCP tool to analyze hit rates and optimization opportunities

5. **Inspect AppleScript Execution**
   Check logs for `osascript` subprocess errors

### Why No Docker Support?

Docker containers on macOS run in a lightweight VM that lacks access to host-level AppleScript and URL scheme handlers. The server requires direct macOS execution to interact with Things 3. Use `uv run server` directly on your Mac instead.

## Version 2.0 Changes

**Breaking Change:** Removed legacy MCP implementation.

If you're upgrading from 1.x:
- Update MCP client configs: `things_server.py` → `things_fast_server.py`
- All tool names and signatures remain unchanged
- You now get all reliability features automatically (caching, circuit breaker, retry logic)

See [CHANGELOG.md](CHANGELOG.md) for complete details.

## Contributing

Contributions are welcome! This project uses the [OpenSpec](openspec/AGENTS.md) workflow for spec-driven development.

**Before contributing:**

1. Read [openspec/project.md](openspec/project.md) for project conventions
2. Check existing [issues](https://github.com/CaseyRo/things-fastmcp/issues) and specs
3. Follow the change proposal workflow for new features
4. Run `ruff check .` and `uv run python -m pytest tests` before submitting PRs

## Migration from Bash Script

If you were previously using the bash script (`./run_things_fastmcp.sh`), here's how to migrate:

**Old way:**
```bash
./run_things_fastmcp.sh
./run_things_fastmcp.sh --host 0.0.0.0 --port 9000
```

**New way:**
```bash
uv run server
THINGS_FASTMCP_HOST=0.0.0.0 THINGS_FASTMCP_PORT=9000 uv run server
```

**Benefits of the new approach:**
- ✅ Simpler command syntax
- ✅ Better dependency management with UV
- ✅ Configuration via `.env` files
- ✅ No bash script maintenance overhead

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits & Acknowledgments

This project builds on the excellent work of:

- **[Harald Lindstrøm](https://github.com/hald)** - Original [things-mcp](https://github.com/hald/things-mcp) implementation
- **[Yaroslav Krempovych](https://github.com/excelsier)** - FastMCP modernization
- **[Cultured Code](https://culturedcode.com)** - Things 3 app and things-py library
- **[Anthropic](https://anthropic.com)** - Model Context Protocol specification and FastMCP framework

## Links

- **Documentation**: [README.md](README.md)
- **Issues & Support**: [GitHub Issues](https://github.com/CaseyRo/things-fastmcp/issues)
- **Privacy Policy**: [PRIVACY.md](PRIVACY.md)
- **Terms of Use**: [TERMS_OF_USE.md](TERMS_OF_USE.md)
- **MCP Specification**: [Model Context Protocol](https://github.com/anthropics/mcp)
- **Things 3 URL Scheme**: [Official Documentation](https://culturedcode.com/things/support/articles/2803573/)
