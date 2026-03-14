## Why

The MCP server has **zero authentication for incoming client requests**. The existing `THINGS_AUTH_TOKEN` is only used outbound (authenticating this server to Things 3 via URL scheme). Any client that can reach the server's network address can call all 21 tools — including write operations that create, modify, and delete tasks.

**Exposure is critical**: the server is reverse-proxied through Caddy at `mcp-things-tmp.cdit-dev.de` (resolved to `0.0.0.0`, TLS via Let's Encrypt) — meaning it is **internet-facing**. Beyond the LAN exposure at `192.168.1.24:8009`, when the upstream is running, the public internet can reach all 21 tools with zero authentication. Caddy itself returns 403 when the upstream is down, but provides no auth layer when it's up.

A full security audit surfaced additional findings beyond the missing auth:

- **AppleScript injection** via crafted tag names in `create-area` — remote code execution on the host
- **World-readable sensitive files** — `config.json` (0644), `.env` (0644), log files (0644) all expose auth tokens
- **Fragile log redaction** — title regex accidentally swallows auth-token by matching across `&` boundaries
- **Exception leakage** — raw `str(e)` returned to MCP clients exposes file paths and internal state
- **Dashboard input validation** — unhandled `ValueError` on `days` param returns 500 with traceback
- **PII in triage data** — `delegated_to` person names stored and served via unauthenticated dashboard
- **DLQ stores task content** — DeadLetterQueue writes titles/notes to world-readable file
- **No security headers** on dashboard HTTP responses

## What Changes

### Authentication

- **BREAKING**: All MCP endpoints (`/mcp`) require a bearer token (`Authorization: Bearer <key>`) by default
- Add `BearerTokenVerifier` using FastMCP 3.x's `TokenVerifier` base class — plugs into `FastMCP(auth=...)` natively
- New `THINGS_MCP_API_KEY` environment variable for configuring the server API key
- Auto-generate a secure API key on first startup if none is set (saved to `.env`)
- Print the API key to console on startup so the user can configure their MCP clients

### Security Hardening

- Fix AppleScript injection in `create-area` tag names — validate and use proper list construction
- Enforce `0600`/`0700` permissions on startup for `.env`, `config.json`, log files, DLQ
- Fix log redaction regex to stop at URL parameter boundaries (`[^&\s]+` instead of `[^;,.]+`)
- Sanitize error messages returned to MCP clients — generic messages, details to logs only
- Validate dashboard `days` parameter — catch `ValueError`, clamp to bounds
- Redact `delegated_to` names from triage data before storage
- Sanitize DLQ entries — strip task content (title, notes) before persisting
- Add security headers to dashboard responses (`X-Frame-Options`, `X-Content-Type-Options`, `CSP`)
- Replace `innerHTML` with `textContent` in dashboard JS where applicable
- Validate `show-in-app` `id` parameter format
- Update `.env.example` with new variable and client configuration examples

## Capabilities

### New Capabilities

- `server-auth`: Bearer token authentication for incoming MCP client requests using FastMCP's native auth provider system
- `security-hardening`: Input validation, file permissions, log redaction, error sanitization, and dashboard hardening

### Modified Capabilities

_(none — this is additive infrastructure, no existing spec requirements change)_

## Impact

- **Code**: New `auth.py` module; changes to `settings.py`, `config.py`, `server_core.py`, `fast_server.py`, `logging_config.py`, `tools_gtd_organize.py`, `tools_utility.py`, `triage_tracker.py`, `utils.py`, `dashboard.html`
- **Clients**: All MCP clients (Claude Desktop, n8n, ChatGPT) must send `Authorization: Bearer <key>` header — client configs need updating
- **Dependencies**: None new — uses FastMCP's built-in `TokenVerifier` and `AccessToken` (already available in 3.1.0)
- **Dashboard**: Gets security headers, input validation, and PII redaction; remains unauthenticated
- **Backwards compatibility**: Breaking for any client not sending the bearer token. Mitigated by auto-generating and printing the key on startup.
