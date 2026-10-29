# Setup

## Prerequisites

- **macOS.** The server drives Things through AppleScript and the Things URL scheme, so it runs as a native process, not in Docker.
- **Things 3** with Things URLs enabled (Things → Settings → General → Enable Things URLs). The token shown there is needed for every write.
- **Python 3.12+** and [uv](https://docs.astral.sh/uv/).

## Install

```bash
git clone https://github.com/CaseyRo/mcp-things.git
cd mcp-things
uv sync

# Store the Things URL token in .env
uv run python scripts/configure_token.py
```

Not published to PyPI; install from source.

## Run

```bash
uv run server        # binds to 127.0.0.1:8009 (`uv run dev` is the same entry point)
```

The MCP endpoint is `http://127.0.0.1:8009/mcp` (streamable HTTP, stateless).
`GET /health` and `GET /healthz` return a small JSON status document and need no
authentication.

On first start the server generates an API key, saves it to `.env` as
`THINGS_MCP_API_KEY` and prints it:

```
  API Key: tmcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  Configure MCP clients with: Authorization: Bearer <key>
```

macOS asks for Automation access to Things the first time a tool runs. The
grant is tied to the Python interpreter in `.venv`; see
[Troubleshooting](troubleshooting.md#a-tool-call-hangs) if you recreate the
environment with a different Python.

## Keep it running with launchd

Add a LaunchAgent such as `~/Library/LaunchAgents/com.example.mcp-things.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.mcp-things</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/mcp-things/.venv/bin/server</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/mcp-things</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>/tmp/mcp-things.err.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.mcp-things.plist
```

Settings are read from `.env` in the working directory. To update, pull, run
`uv sync --locked` and restart the job with
`launchctl kickstart -k gui/$(id -u)/com.example.mcp-things`.

## Configuration

Settings come from environment variables or `.env` (see `.env.example`).

| Variable | Default | Purpose |
|----------|---------|---------|
| `THINGS_MCP_HOST` | `127.0.0.1` | Bind address |
| `THINGS_MCP_PORT` | `8009` | Listen port |
| `THINGS_MCP_TRANSPORT` | `streamable-http` | Transport (the only supported value) |
| `THINGS_AUTH_TOKEN` | empty | Things URL scheme token; required for write tools |
| `THINGS_MCP_API_KEY` | auto-generated | Bearer token clients must send |
| `THINGS_MCP_PUBLIC_URL` | unset | Public HTTPS URL of the server, used as the auth base URL behind a proxy |
| `THINGS_MCP_DEBUG` | `false` | Verbose console logging |
| `THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT` | `false` | Bring Things to the foreground during AppleScript calls (debugging) |
| `RETRY_ATTEMPTS` | `3` | Retries for failed operations (1 to 10) |
| `RETRY_DELAY` | `1.0` | Seconds between retries |
| `THINGSDB` | auto-detected | Path to the Things SQLite database |

## Authentication

Every MCP request needs `Authorization: Bearer <THINGS_MCP_API_KEY>`. Write
tools additionally need `THINGS_AUTH_TOKEN`.

- **First run:** a `tmcp_` key is generated and saved to `.env`.
- **Regenerate:** delete the `THINGS_MCP_API_KEY=` line from `.env` and restart.
- **Set your own:** put `THINGS_MCP_API_KEY=your-key` in `.env` before starting.

## Connect a client

### Claude Code

```bash
claude mcp add --transport http --header "Authorization: Bearer tmcp_your-key" things http://127.0.0.1:8009/mcp
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "things": {
      "url": "http://127.0.0.1:8009/mcp",
      "headers": { "Authorization": "Bearer tmcp_your-key" }
    }
  }
}
```

If your Claude Desktop version doesn't support `url`, bridge with `mcp-remote`:

```json
{
  "mcpServers": {
    "things": {
      "command": "npx",
      "args": ["mcp-remote", "--header", "Authorization: Bearer tmcp_your-key", "http://127.0.0.1:8009/mcp"]
    }
  }
}
```

### ChatGPT and n8n

Both work over the same endpoint. The server adapts tool schemas per client;
the details and known quirks are in [clients/chatgpt.md](clients/chatgpt.md)
and [clients/n8n.md](clients/n8n.md).

## Reaching it from another machine

Keep the server on loopback and put an authenticating tunnel or reverse proxy
in front of it (Tailscale, Cloudflare Tunnel with Access, or similar). Set
`THINGS_MCP_PUBLIC_URL` to the public URL. The bearer key still applies.
