# Things 3 GTD MCP Server

A **Model Context Protocol (MCP) server** for [Things 3](https://culturedcode.com/things/) that brings GTD (Getting Things Done) methodology to AI assistants.

> **Note:** Review the [Privacy Notice](PRIVACY.md) and [Terms of Use](TERMS_OF_USE.md) before installation.

## What Is This?

This MCP server enables AI assistants like Claude to manage your tasks in Things 3 using natural language. But more than just a task API, it's designed around David Allen's **GTD methodology** — helping you capture, clarify, organize, reflect, and engage with your work the way GTD intended.

### The Vision

> "Your head's a crappy office." — David Allen

The goal isn't to expose database operations to an AI. It's to give AI assistants the tools to help you *practice GTD* effectively:

- **Capture** thoughts quickly without organizing
- **Clarify** inbox items with GTD decision guidance
- **Organize** tasks by context, energy, and time available
- **Reflect** with daily and weekly reviews that surface stalled projects
- **Engage** by finding the right task for your current context

## History

This project evolved through several stages:

1. **[things-mcp](https://github.com/hald/things-mcp)** by Harald Lindstrøm — Original MCP implementation exposing Things 3 operations
2. **FastMCP Migration** — Modernized to FastMCP framework with async tools, caching, and reliability features
3. **GTD-Native Tools** — Redesigned from REST-style CRUD operations to intent-based tools aligned with GTD's five stages

The shift from "database wrapper" to "GTD assistant" reflects a key insight about MCP design: **tools should match how agents think about problems**, not how APIs are structured.

## Future Direction

This is an evolving experiment in GTD-native AI tooling. Potential directions:

- **MCP Resources** for ambient GTD state (inbox count, stalled projects)
- **Smarter context detection** based on time, location, calendar
- **GTD coaching** — proactive suggestions during reviews
- **Multi-app GTD** — extending the pattern beyond Things 3

Contributions and ideas welcome.

## Quick Start

### Prerequisites

- **macOS** (required — uses AppleScript and URL schemes)
- **Things 3** with scripting permissions enabled
- **Python 3.12+**
- **uv** package manager

### Installation

```bash
# Clone and install
git clone https://github.com/CaseyRo/things-fastmcp.git
cd things-fastmcp
uv pip install -e .

# Configure Things 3 authentication token
python configure_token.py
```

### Running

```bash
# Production mode (binds to 127.0.0.1:8009)
uv run server

# Development mode with auto-reload
uv run dev
```

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "things": {
      "command": "uv",
      "args": ["run", "server"]
    }
  }
}
```

## GTD Tools

The server provides **12 GTD-native tools** organized by methodology stage:

### Capture
| Tool | Purpose |
|------|---------|
| `capture-task` | Quick capture to Inbox without organizing |

### Clarify
| Tool | Purpose |
|------|---------|
| `process-inbox` | Process oldest inbox item with GTD decision guidance |
| `convert-to-project` | Transform a task into a multi-step project |

### Organize
| Tool | Purpose |
|------|---------|
| `schedule-task` | Create organized tasks with context, dates, projects |
| `delegate-task` | Mark task as "Waiting For" with person and follow-up |
| `defer-task` | Move to Someday/Maybe or schedule for future date |
| `plan-project` | Create project with initial tasks atomically |

### Reflect
| Tool | Purpose |
|------|---------|
| `daily-review` | Today's tasks, overdue items, inbox status |
| `weekly-review` | Stalled projects, waiting-for items, someday review |

### Engage
| Tool | Purpose |
|------|---------|
| `get-tasks` | Context-first task retrieval (replaces 7 view tools) |
| `focus-mode` | Get single most important task for current context |
| `complete-task` | Mark task done by ID or fuzzy title match |

Plus `search-tasks` for full-text and filtered search.

### GTD Context Tags

For best results, use consistent GTD tags in Things 3:

```
Contexts: @computer, @phone, @office, @home, @errands, @anywhere
Energy:   high-energy, low-energy
Time:     5min, 15min, 30min, 1hr+
Status:   waiting-for
People:   @person-name (for agenda items)
```

## Repository Structure

| File/Directory | Purpose |
|----------------|---------|
| `README.md` | This file — project overview and quick start |
| `DEVELOPERS.md` | Developer guide — setup, architecture, testing, contributing |
| `CLAUDE.md` | AI assistant instructions for working in this codebase |
| `openspec/` | Spec-driven development framework and change proposals |
| `src/things_mcp/` | Main source code |
| `tests/` | Test suite (unit + integration) |
| `PRIVACY.md` | Privacy notice |
| `TERMS_OF_USE.md` | Terms of use |
| `MIGRATION.md` | Migration guide from previous versions |
| `CHANGELOG.md` | Version history |
| `node-red-flow.json` | Node-RED proxy flow for remote access via Tailscale (forwards mcp-session-id headers) |

### Key Source Files

```
src/things_mcp/
├── fast_server.py        # FastMCP server + 12 GTD tool definitions
├── url_scheme.py         # Things URL scheme builders (write operations)
├── applescript_bridge.py # AppleScript execution layer
├── formatters.py         # Output formatting for responses
├── cache.py              # @cached decorator for read operations
├── utils.py              # Circuit breaker, rate limiter, helpers
└── tag_handler.py        # Auto-creates missing tags
```

### OpenSpec

This project uses **OpenSpec** for spec-driven development. The `openspec/` directory contains:

- `project.md` — Project conventions and architecture
- `AGENTS.md` — Instructions for AI assistants working on changes
- `changes/` — Active and archived change proposals

When planning significant changes, create a proposal in `openspec/changes/<change-id>/` with design docs and requirement specs before implementation.

## Development

For development setup, architecture details, testing, and contribution guidelines, see **[DEVELOPERS.md](DEVELOPERS.md)**.

Quick commands:

```bash
# Run tests (requires Things 3)
uv run python -m pytest tests -v

# Run unit tests only (CI/CD safe)
uv run python -m pytest tests -m "not real"

# Lint and format
uv run ruff check . && uv run ruff format .
```

## Credits

- **[Harald Lindstrøm](https://github.com/hald)** — Original things-mcp
- **[Jonathan Lowin](https://github.com/jlowin)** — FastMCP framework
- **[things.py](https://github.com/thingsapi/things.py)** — Things 3 Python library
- **[David Allen](https://gettingthingsdone.com/)** — GTD methodology
- **[Cultured Code](https://culturedcode.com)** — Things 3

## License

MIT License — see [LICENSE](LICENSE).

## Links

- [GitHub Issues](https://github.com/CaseyRo/things-fastmcp/issues)
- [FastMCP Documentation](https://gofastmcp.com)
- [Things 3 URL Scheme](https://culturedcode.com/things/support/articles/2803573/)
- [GTD Methodology](https://gettingthingsdone.com/)
