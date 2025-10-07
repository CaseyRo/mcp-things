# Privacy Notice

_Last updated: 2025-10-07_

The Things FastMCP server is designed to run entirely on your macOS device. It never sends your task data to the maintainers or to any third-party service beyond the Model Context Protocol (MCP) client you authorize. This notice explains what information the server accesses, how it is stored, and how you can remove it.

## Data the server can access

When you start the server you grant it permission to interact with the local Things 3 application via AppleScript and the official URL scheme. Depending on the tools you invoke, the server may read or modify the following information that already lives in your Things app:

- Task, project, checklist, and area titles, notes, tags, deadlines, and completion status
- Metadata such as creation dates, reminders, and linked items exposed by the Things API
- Task identifiers that Things uses to reference individual records

The server also requires a Things authentication token so that URL commands can be executed. You provide this token explicitly via the `configure_token.py` helper or the `THINGS_AUTH_TOKEN` environment variable.

## Local storage and logging

All persistent data is stored locally on the same macOS account that runs the server:

- The authentication token and runtime settings are written to `~/.things-mcp/config.json` when you run `configure_token.py` or when the configuration module saves updates.
- The server writes runtime information, warnings, and errors to the terminal. If you redirect logs to a file, the contents remain on your machine.
- Optional debugging artifacts such as the dead-letter queue (`things_dlq.json`) or cache snapshots are created in the project directory when the related features are enabled.

No telemetry, analytics, or remote logging is performed by default. Network traffic initiated by the server is limited to the MCP protocol messages exchanged with the client that you launch (for example, Claude Desktop) and to any integrations you explicitly configure.

## Data retention and deletion

Because all storage is local, you control retention. To remove sensitive data you can:

1. Delete `~/.things-mcp/config.json` to clear the saved Things authentication token and reset configuration values. The file will be recreated with defaults the next time the server starts.
2. Delete `things_dlq.json`, cache files, or any other artifacts you created during debugging.
3. Uninstall the repository directory to remove the code and any local virtual environments.
4. Revoke the Things authentication token inside the Things macOS app if you believe it has been exposed.

Restart the server after deleting configuration files so that it regenerates clean defaults. If you are unsure which files to delete, search for items created at the time you ran the server and remove them manually.

## Questions and contact

This project is community-maintained. Report privacy issues or questions by opening a GitHub issue in the repository. Do not include personal or task data in public issue descriptions—sanitize examples before sharing them.
