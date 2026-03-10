# Privacy Notice

_Last updated: 2026-03-10_

The Things MCP server is **open-source, self-hosted software**. It runs entirely on your macOS device. The project maintainers do not receive, process, store, or have access to any of your data — ever.

## Your responsibility

**You are the data controller.** By self-hosting this software, you (or your organization) assume full responsibility for any personal data processed by it. The project maintainers provide functionality only — they are neither data controller nor data processor under GDPR/DSGVO or any other privacy regulation.

If you process data belonging to third parties (clients, employees, etc.) through this software, it is your responsibility to:

- Ensure you have a lawful basis for processing (GDPR Art. 6)
- Maintain appropriate records of processing activities (GDPR Art. 30)
- Update your data processing agreements (AVV) if applicable
- Implement appropriate technical and organizational measures (GDPR Art. 32)

## Data the server accesses

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
- **Triage history**: If triage tracking is active, anonymized action records are stored in `~/.things-mcp/triage_history.json`. These records contain only action types, computed categories, and timestamps — **no task titles, notes, or personal content is stored**. Records are retained indefinitely for long-term trend analysis. You can delete this file at any time.
- **Debugging artifacts**: Optional debugging artifacts such as the dead-letter queue (`things_dlq.json`) are created in the project directory when related features are enabled.

**File permissions**: All files in `~/.things-mcp/` are created with restrictive permissions (`0600` for files, `0700` for directories) to prevent access by other users on shared systems.

No telemetry, analytics, or remote logging is performed. Network traffic initiated by the server is limited to the MCP protocol messages exchanged with the client that you launch (for example, Claude Desktop, n8n, or ChatGPT) and to any integrations you explicitly configure.

## Data retention and deletion

Because all storage is local, you control retention. To remove data you can:

1. Delete `.env` file in the project directory to clear environment-based configuration.
2. Delete `~/.things-mcp/config.json` to clear the legacy saved Things authentication token.
3. Delete `~/.things-mcp/logs/` directory to remove all log files.
4. Delete `~/.things-mcp/triage_history.json` to remove all triage tracking data.
5. Delete `things_dlq.json`, cache files, or any other artifacts created during debugging.
6. Uninstall the repository directory to remove the code and any local virtual environments.
7. Revoke the Things authentication token inside the Things macOS app if you believe it has been exposed.

Restart the server after deleting configuration files so that it regenerates clean defaults.

## No warranty

This software is provided "as is" under the MIT license. The project maintainers make no representations about the suitability of this software for processing personal data. You are solely responsible for evaluating whether this software meets your regulatory and compliance requirements.

## Questions and contact

This project is community-maintained. Report privacy issues or questions by opening a GitHub issue in the repository. Do not include personal or task data in public issue descriptions — sanitize examples before sharing them.
