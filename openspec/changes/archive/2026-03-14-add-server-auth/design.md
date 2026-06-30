## Context

The Things MCP server (FastMCP 3.1.0, streamable-http) exposes 21 GTD tools with zero authentication for incoming requests. The `THINGS_AUTH_TOKEN` only authenticates outbound calls to Things 3 via URL scheme. The server is internet-facing via a Caddy reverse proxy at a public hostname. When the upstream is running, all tools — including write operations (capture, modify, complete, delete tasks) — are callable by anyone.

A security audit revealed additional vulnerabilities beyond missing auth: AppleScript injection via tag names (RCE), world-readable sensitive files, fragile log redaction, exception details leaked to clients, dashboard input validation gaps, PII in triage data, and missing security headers.

FastMCP 3.1.0 provides a native auth system: `TokenVerifier` base class → `verify_token()` → `AccessToken`, wired in via `FastMCP(auth=...)`. This handles bearer token extraction, middleware injection, and 401 responses automatically.

## Goals / Non-Goals

**Goals:**

- Require bearer token authentication for all MCP endpoints (`/mcp`)
- Use FastMCP's native `TokenVerifier` auth provider (no custom ASGI middleware)
- Auto-generate a secure API key on first startup if none is configured
- Persist generated key to `.env` so it survives restarts
- Print the key to console on startup for easy client configuration
- Keep the dashboard (`/dashboard`) unauthenticated (read-only triage data)
- Fix all CRITICAL and HIGH findings from the security audit
- Fix MEDIUM findings where practical

**Non-Goals:**

- OAuth2 / OIDC provider — overkill for a single-user macOS tool
- Per-tool or scope-based authorization — all-or-nothing access is sufficient
- Multi-user / multi-key support — single key is appropriate for this use case
- Rate limiting or IP allowlisting — separate concern, not part of this change
- Caddy-level auth configuration — out of scope (server should protect itself)

## Decisions

### 1. FastMCP `TokenVerifier` subclass (not custom ASGI middleware)

FastMCP 3.x provides `TokenVerifier` → `verify_token(token: str) -> AccessToken | None`. Subclassing this and passing it to `FastMCP(auth=verifier)` gives us bearer token validation with zero custom middleware — FastMCP handles the `Authorization` header parsing, 401 responses, and the `BearerAuthBackend` Starlette middleware automatically.

**Alternative considered**: Custom Starlette middleware in `_create_combined_app()`. Rejected because it duplicates what FastMCP already provides, and would need manual header parsing and error response formatting.

### 2. Static API key with constant-time comparison (not JWT)

A single static API key validated with `hmac.compare_digest()` is appropriate for a single-user, self-hosted tool. JWTs add complexity (signing keys, expiration, claims) with no benefit here.

**Alternative considered**: JWT with shared secret. Rejected — no multi-user, no token expiration, no claims needed.

### 3. `THINGS_MCP_API_KEY` env var with auto-generation

New env var `THINGS_MCP_API_KEY`. If empty on startup, generate a `tmcp_<urlsafe-base64-32>` key, write it to `.env`, and print it to console. This ensures zero-config security — the server is never unprotected after first run.

**Alternative considered**: Require manual key configuration (fail if missing). Rejected — too much friction; users would skip it and run unprotected.

### 4. New `auth.py` module (not inline in server_core.py)

Keeps auth concerns isolated. Contains `BearerTokenVerifier` class and `generate_api_key()` helper. Clean separation from client compatibility middleware.

### 5. Dashboard stays unauthenticated but gets hardened

The dashboard is a separate Starlette route outside the MCP mount. FastMCP's auth only applies to the `/mcp` mount point, so the dashboard is naturally excluded. However, the audit revealed PII leakage (`delegated_to` names) and missing security headers. The dashboard will be hardened:

- Redact `delegated_to` before storing in triage data
- Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`
- Validate and clamp `days` query parameter
- Replace `innerHTML` with `textContent` where data is text-only

### 6. AppleScript injection fix — validate + proper list construction

The `create-area` tool builds an AppleScript string with tag names that can escape the string literal. Fix with two layers:

1. **Input validation**: tag names must match `^[@\w\s\-]+$` (word chars, spaces, hyphens, `@` prefix)
2. **Proper AppleScript list**: use `{\"tag1\", \"tag2\"}` list syntax instead of embedding in a single string

### 7. Error sanitization — generic messages to clients, details to logs

All `except Exception as e` blocks currently pass `str(e)` to `ToolError`. This leaks file paths, SQL errors, and internal state. Change to:

- Log full exception with `exc_info=True` for debugging
- Return generic error message to client: `"Failed to <operation>. Check server logs for details."`
- Only pass `str(e)` for intentionally-raised `ToolError`/`ValueError` that are already sanitized

### 8. Startup permission enforcement

Rather than trusting that files were created with correct permissions, enforce on every startup:

- `.env` → `0600`
- `~/.things-mcp/config.json` → `0600`, directory → `0700`
- Log files → `0600`, log directory → `0700`
- DLQ file → `0600`

### 9. Log redaction regex fix

The title redaction pattern `(title\s*[:=]\s*)([^;,.]+)` matches across `&` boundaries, accidentally consuming `auth-token=` values. Fix to `[^&;\s]+` to stop at URL parameter boundaries. This makes the auth-token pattern on the next line actually fire independently.

### 10. DLQ content sanitization

`DeadLetterQueue.add_failed_operation()` stores raw `params` dict including task titles and notes. Strip sensitive fields (`title`, `notes`, `checklist-items`, `prepend-notes`, `append-notes`) before persisting — replace with `[REDACTED]`.

## Risks / Trade-offs

- **[Client breakage]** → All existing MCP client configs must add the bearer token. Mitigated by printing the key prominently on startup and documenting client config examples in `.env.example`.

- **[Key in .env file]** → The API key is stored in plaintext in `.env`. Mitigated by enforcing `0600` file permissions on startup.

- **[Auto-generated key opacity]** → User might not notice the key printed to console on first run. Mitigated by using a clear, boxed startup message and logging at WARNING level.

- **[Lost key]** → If user loses the key, they can read it from `.env` or delete the line to trigger regeneration on next startup.

- **[Tag validation strictness]** → The `^[@\w\s\-]+$` regex may reject legitimate tag names with special characters (e.g., `#focus` or `project/subproject`). Start strict, relax if users report issues.

- **[Error message opacity]** → Generic error messages make debugging harder for MCP client users. Mitigated by including clear log references and ensuring the server debug mode provides detailed console output.
