# Things 3 Enhanced MCP

This repository provides a Model Context Protocol (MCP) server for [Things](https://culturedcode.com/things/).

> **Important:** Review the [Privacy Notice](PRIVACY.md) and [Terms of Use](TERMS_OF_USE.md) before running or deploying the server.

It exposes a set of tools that allow AI assistants or automation platforms—for example Claude Desktop or n8n—to read and modify your tasks, projects and areas via the Things URL scheme.

The codebase contains a modern implementation using the **FastMCP** pattern. It offers improved reliability features such as caching, rate limiting and an AppleScript fallback. A legacy `things_server.py` still exists for compatibility but will be removed by the end of the year.

## Why Things MCP?

This server unlocks the power of AI or automated workflows for your task management:

- **Natural Language Task Creation**: Create tasks with full details in natural language
- **Smart Task Analysis**: Gain insights into your projects and productivity patterns
- **GTD & Productivity Workflows**: Implement productivity systems using your preferred tools
- **Seamless Integration**: Works directly with your existing Things 3 data

## Features

- Access to all major Things lists (Inbox, Today, Upcoming, etc.)
- Project and area management
- Tag operations
- Advanced search capabilities
- Recent items tracking
- Detailed item information including checklists
- Support for nested data (projects within areas, todos within projects)
- FastMCP based server entry point [`things_fast_server.py`](things_fast_server.py) that calls `run_things_mcp_server()` from the library
- Legacy standard MCP implementation in [`things_server.py`](things_server.py) for compatibility
- Rich set of tools for listing, searching and modifying Things items (see `src/things_mcp/fast_server.py` for decorators)

## Quick start

Before installing dependencies or launching the server, confirm you have read the [Privacy Notice](PRIVACY.md) and [Terms of Use](TERMS_OF_USE.md).

1. Clone this repository and install it in editable mode using [uv](https://github.com/astral-sh/uv).
   If you don't have `uv` installed yet, run `pipx install uv` (or `pip install uv`).
   ```bash
   git clone https://github.com/CaseyRo/things-fastmcp.git
   cd things-fastmcp
   uv pip install -e .
   ```
   *(The helper script in step 3 will also bootstrap a uv virtual environment if you skip this install step.)*
2. Configure your Things authentication token:
   ```bash
   python configure_token.py
   ```
3. Run the server (creates or reuses a uv-managed virtual environment and falls back to system Python if `uv` is unavailable):
   ```bash
   ./run_things_fastmcp.sh
   ```
   The FastMCP server listens on `http://0.0.0.0:8009` and uses [Rich](https://github.com/Textualize/rich) for colorful terminal output.
   Alternatively, use:
   ```bash
   mcp dev things_fast_server.py
   ```
   The `mcp dev` command uses the [MCP development helper](https://github.com/anthropics/mcp-cli#development-helper) for auto-reload during development.

### Why not Docker?

The server interacts with the native Things application through AppleScript and the `open` command. Docker containers on macOS run inside a lightweight VM and don't have access to these host-level scripting capabilities. As a result the MCP server must run directly on macOS rather than inside a Docker container.

## Development

Use `mcp dev` from the [MCP development helper](https://github.com/anthropics/mcp-cli#development-helper) to run the server from source:

```bash
mcp dev things_fast_server.py
```

The traditional implementation in `things_server.py` can still be started the same way, but it is no longer actively maintained. It will be removed by EOY 2025.

## Deprecation notice

The old MCP server (`things_server.py`) will be removed by the end of 2025. Please migrate any workflows to the FastMCP implementation.

### Advanced Debugging

1. **Check Dead Letter Queue**: Failed operations are stored in `things_dlq.json`
2. **Monitor Circuit Breaker**: Look for "Circuit breaker" messages in logs
3. **Cache Performance**: Use `get-cache-stats` tool to check hit rates
4. **Enable Debug Logging**: Set console level to DEBUG in `logging_config.py`

## Tribute

This project builds on work by others. The original version was [things-mcp](https://github.com/hald/things-mcp) created by Harald Lindstrøm.
Later, [Yaroslav Krempovych](https://github.com/excelsier/things-fastmcp) modernized it with a FastMCP implementation.

