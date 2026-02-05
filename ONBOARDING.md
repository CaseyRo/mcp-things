# Welcome to Things FastMCP! 🎉

## ✅ Setup Complete

Your development environment has been configured:

- ✅ **Python 3.14.2** (meets 3.12+ requirement)
- ✅ **uv package manager** installed
- ✅ **Dependencies installed** (`uv pip install -e .`)
- ✅ **Things 3** installed and running
- ✅ **`.env` file** created from template

## 🔑 Next Steps

### 1. Configure Things Authentication Token

The server requires a Things authentication token for write operations (create, update, delete). Get it from:

**Things 3 → Settings → General → Enable Things URLs**

Then run:

```bash
python scripts/configure_token.py
```

This will prompt you for your token and save it to your configuration.

**Important:** Without this token, write operations will fail silently. The token is stored locally and never transmitted externally.

### 2. Test the Server

Start the server in development mode:

```bash
uv run dev
```

Or in production mode:

```bash
uv run server
```

The server will bind to `http://127.0.0.1:8009` by default.

### 3. Verify Installation

Run the CI-safe test suite (no Things 3 required):

```bash
uv run python -m pytest tests
```

For real integration tests (requires Things 3):

```bash
uv run python -m pytest tests -m real
```

## 📚 Project Overview

### What Is This?

A **Model Context Protocol (MCP) server** for Things 3 that enables AI assistants (Claude, ChatGPT, etc.) to manage your tasks using natural language. The tools are designed around **GTD (Getting Things Done)** methodology.

### Architecture

```
Read Operations:  MCP Client → FastMCP → things-py (SQLite) → cache → response
Write Operations: MCP Client → FastMCP → URL scheme → macOS `open` → Things app
```

### Key Files

- `src/things_mcp/fast_server.py` - Main server with all 19 GTD tools
- `src/things_mcp/tools_gtd_*.py` - Tools organized by GTD stage
- `src/things_mcp/url_scheme.py` - Things URL scheme builders
- `docs/DEVELOPERS.md` - Complete developer guide
- `CLAUDE.md` - Quick reference for AI assistants

### GTD Tools (19 total)

**Capture** (1): `capture-task`
**Clarify** (2): `process-inbox`, `convert-to-project`
**Organize** (5): `schedule-task`, `delegate-task`, `defer-task`, `plan-project`, `modify-task`
**Reflect** (2): `daily-review`, `weekly-review`
**Engage** (3): `get-tasks`, `focus-mode`, `complete-task`
**Utility** (6): `search-tasks`, `get-projects`, `get-areas`, `get-tags`, `show-in-app`, `get-cache-stats`

## 🛠️ Development Workflow

### Common Commands

```bash
# Run server
uv run server              # Production mode
uv run dev                 # Development mode with auto-reload

# Testing
uv run python -m pytest tests                    # CI-safe (default)
uv run python -m pytest tests -m real            # Real integration tests
uv run python -m pytest tests --cov=src/things_mcp --cov-report=term-missing

# Code Quality
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

### Code Style

- Use **Ruff** for linting and formatting
- Follow PEP 8 conventions (snake_case for functions/variables)
- Use type hints extensively
- Never log task titles/notes (privacy)
- Run `ruff check .` and `pytest` after modifications

### OpenSpec Workflow

This project uses **OpenSpec** for spec-driven development:

- Review `openspec/project.md` for conventions
- Create proposals in `openspec/changes/<change-id>/`
- See `CLAUDE.md` for OpenSpec commands

## 🔧 Configuration

### Environment Variables

Edit `.env` to customize:

```bash
THINGS_FASTMCP_HOST=127.0.0.1    # Server bind address (default: localhost)
THINGS_FASTMCP_PORT=8009         # Server port
THINGS_AUTH_TOKEN=your-token     # REQUIRED: Get from Things settings
THINGS_MCP_DEBUG=false           # Enable verbose debug logging
```

### Transport

- **Streamable-HTTP** transport only (SSE removed)
- Endpoint: `/mcp`
- Compatible with: Claude Desktop, n8n, ChatGPT

## 📖 Documentation

- **[README.md](README.md)** - Project overview and quick start
- **[docs/DEVELOPERS.md](docs/DEVELOPERS.md)** - Complete developer guide
- **[CLAUDE.md](CLAUDE.md)** - Quick reference for AI assistants
- **[docs/TESTING.md](docs/TESTING.md)** - Testing guide
- **[openspec/project.md](openspec/project.md)** - Project conventions

## 🚀 Quick Test

After configuring your token, test the server:

```bash
# Start server
uv run dev

# In another terminal, test with curl
curl http://127.0.0.1:8009/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 🐛 Troubleshooting

### Server Won't Start

- Verify Things 3 is installed and running
- Check Python version: `python --version` (requires 3.12+)
- Review logs for error messages

### Operations Failing

- Ensure `THINGS_AUTH_TOKEN` is configured
- Check Things has automation permissions (System Settings → Privacy & Security)
- Review Dead Letter Queue: `cat things_dlq.json` (if exists)

### Debug Mode

```bash
# Show Things in foreground during operations
export THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT=1

# Enable debug logging
export THINGS_MCP_DEBUG=true
```

## 📝 Next Actions

1. **Configure token**: `python scripts/configure_token.py`
2. **Test server**: `uv run dev`
3. **Run tests**: `uv run python -m pytest tests`
4. **Read docs**: Check `docs/DEVELOPERS.md` for architecture details
5. **Explore tools**: See `src/things_mcp/fast_server.py` for all 19 GTD tools

## 🎯 Key Concepts

- **GTD-Native**: Tools match GTD methodology, not database operations
- **Privacy-First**: All data stays local, sensitive content never logged
- **macOS Only**: Requires AppleScript and URL scheme access
- **FastMCP 3.0**: Modern async-first MCP framework
- **Caching**: Read operations cached with TTL-based invalidation

---

**Welcome aboard!** 🚢

For questions or issues, see [GitHub Issues](https://github.com/CaseyRo/things-fastmcp/issues).
