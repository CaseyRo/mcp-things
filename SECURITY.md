# Security

## Reporting a vulnerability

Please report privately through [GitHub security advisories](https://github.com/CaseyRo/mcp-things/security/advisories/new), not in a public issue.

Relevant reports include an authentication bypass on `/mcp`, the API key or Things token showing up in logs or responses, task content leaking into logs, and command injection through tool arguments into AppleScript or the URL scheme.

## Supported versions

Only the latest `v*` tag on the `source` branch gets fixes.

## Running it safely

- Keep the server bound to `127.0.0.1` and put an authenticating tunnel or proxy in front of it for remote access.
- Treat `THINGS_MCP_API_KEY` like a password: anyone with it can read and change your Things.
