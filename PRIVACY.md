# Privacy Notice

_Last updated: 2026-02-05_

The Things FastMCP server is designed to run entirely on your macOS device. It never sends your task data to the maintainers or to any third-party service beyond the Model Context Protocol (MCP) client you authorize. This notice explains what information the server accesses, how it is stored, and how you can remove it.

## Data the server can access

When you start the server you grant it permission to interact with the local Things 3 application via AppleScript and the official URL scheme. Depending on the tools you invoke, the server may read or modify the following information that already lives in your Things app:

- Task, project, checklist, and area titles, notes, tags, deadlines, and completion status
- Metadata such as creation dates, reminders, and linked items exposed by the Things API
- Task identifiers that Things uses to reference individual records

The server also requires a Things authentication token so that URL commands can be executed. You provide this token explicitly via the `THINGS_AUTH_TOKEN` environment variable (recommended, stored in `.env` file) or via the `scripts/configure_token.py` helper (saves to `~/.things-mcp/config.json` for backwards compatibility).

## Local storage and logging

All persistent data is stored locally on the same macOS account that runs the server:

- **Configuration**: The authentication token and runtime settings can be stored in:
  - `.env` file in the project directory (preferred method, via pydantic-settings)
  - `~/.things-mcp/config.json` (legacy method, created by `scripts/configure_token.py`)
- **Logging**: The server automatically creates log files in `~/.things-mcp/logs/`:
  - `things_mcp.log` - Human-readable logs with rotation (10MB max, 5 backups)
  - `things_mcp_errors.log` - Error-level logs only
  - `things_mcp_structured.json` - Structured JSON logs for analysis
  - Logs are automatically redacted to exclude sensitive task data (titles, notes, etc.)
- **Debugging artifacts**: Optional debugging artifacts such as the dead-letter queue (`things_dlq.json`) are created in the project directory when related features are enabled.

No telemetry, analytics, or remote logging is performed by default. Network traffic initiated by the server is limited to the MCP protocol messages exchanged with the client that you launch (for example, Claude Desktop, n8n, or ChatGPT) and to any integrations you explicitly configure.

## Data retention and deletion

Because all storage is local, you control retention. To remove sensitive data you can:

1. Delete `.env` file in the project directory to clear environment-based configuration.
2. Delete `~/.things-mcp/config.json` to clear the legacy saved Things authentication token and reset configuration values. The file will be recreated with defaults the next time the server starts if you use `scripts/configure_token.py`.
3. Delete `~/.things-mcp/logs/` directory to remove all log files.
4. Delete `things_dlq.json`, cache files, or any other artifacts you created during debugging.
5. Uninstall the repository directory to remove the code and any local virtual environments.
6. Revoke the Things authentication token inside the Things macOS app if you believe it has been exposed.

Restart the server after deleting configuration files so that it regenerates clean defaults. If you are unsure which files to delete, search for items created at the time you ran the server and remove them manually.

## Questions and contact

This project is community-maintained. Report privacy issues or questions by opening a GitHub issue in the repository. Do not include personal or task data in public issue descriptions—sanitize examples before sharing them.
