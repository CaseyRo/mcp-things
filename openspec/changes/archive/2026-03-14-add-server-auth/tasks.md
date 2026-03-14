## 1. Auth Module

- [x] 1.1 Create `src/things_mcp/auth.py` with `BearerTokenVerifier(TokenVerifier)` subclass — `verify_token()` using `hmac.compare_digest()`, returns `AccessToken` on match, `None` on mismatch
- [x] 1.2 Add `generate_api_key()` function returning `tmcp_<secrets.token_urlsafe(32)>`

## 2. Settings & Configuration

- [x] 2.1 Add `things_mcp_api_key: str` field to `Settings` in `settings.py` with `has_api_key` property and `get_api_key()` convenience function
- [x] 2.2 Add `ensure_api_key()` to `config.py` — reads existing key or generates + saves to `.env` (extract `_write_env_var` helper, refactor `_write_token_to_env` to use it)
- [x] 2.3 Update `.env.example` with `THINGS_MCP_API_KEY` variable and client configuration notes

## 3. Server Integration

- [x] 3.1 Wire `BearerTokenVerifier` into `create_mcp_server()` in `server_core.py` — pass as `auth=` parameter to `FastMCP()`
- [x] 3.2 Call `ensure_api_key()` in `run_things_mcp_server()` in `fast_server.py` before server creation, print key to console at startup
- [x] 3.3 Replace the existing "SECURITY WARNING" log with an auth-enabled confirmation message when API key is active

## 4. AppleScript Injection Fix (CRITICAL)

- [x] 4.1 Add tag name validation function — reject names not matching `^[@\w\s\-]+$`, raise `ToolError`
- [x] 4.2 Fix `create-area` in `tools_gtd_organize.py` — use proper AppleScript list construction `{"tag1", "tag2"}` instead of string interpolation
- [x] 4.3 Audit all other AppleScript-generating code for the same tag name injection pattern (ensure_tags_exist, etc.)

## 5. File Permission Hardening (CRITICAL)

- [x] 5.1 Add startup permission enforcement in `fast_server.py` — check and fix `.env` (0600), `~/.things-mcp/config.json` (0600), config dir (0700)
- [x] 5.2 Fix `logging_config.py` — set log directory to 0700 and log files to 0600 on creation
- [x] 5.3 Fix `utils.py` DeadLetterQueue `_save_queue()` — set 0600 on DLQ file after writing

## 6. Log Redaction Fix (CRITICAL)

- [x] 6.1 Fix title redaction regex in `logging_config.py` — change `[^;,.]+` to `[^&;\s]+` to stop at URL parameter boundaries
- [x] 6.2 Verify auth-token pattern fires independently when title no longer consumes it

## 7. Error Sanitization (HIGH)

- [x] 7.1 Update all tool `except Exception as e` blocks — log with `exc_info=True`, return generic message to client
- [x] 7.2 Preserve deliberate `ToolError`/`ValueError` messages that are already safe

## 8. Dashboard Hardening (HIGH + MEDIUM)

- [x] 8.1 Wrap `int(request.query_params.get("days"))` in try/except with clamp to 0-365 in both dashboard routes
- [x] 8.2 Add security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`) to dashboard responses
- [x] 8.3 Replace `innerHTML` with `textContent` in `dashboard.html` where rendering text-only data

## 9. PII & Content Redaction (MEDIUM)

- [x] 9.1 Redact `delegated_to` from triage `action_details` before storage in `triage_tracker.py`
- [x] 9.2 Add `_sanitize_params()` to DeadLetterQueue — strip `title`, `notes`, `checklist-items`, `prepend-notes`, `append-notes` before persisting
- [x] 9.3 Validate `show-in-app` `id` parameter — accept Things UUIDs and known list names, reject other formats

## 10. Documentation & Client Config

- [x] 10.1 Update `CLAUDE.md` — add `THINGS_MCP_API_KEY` to environment variables section, update client setup notes with bearer token header
- [ ] 10.2 Update README client configuration examples to include `Authorization: Bearer <key>` header

## 11. Testing

- [x] 11.1 Test: server rejects requests to `/mcp` without bearer token (HTTP 401)
- [ ] 11.2 Test: server accepts requests to `/mcp` with valid bearer token
- [ ] 11.3 Test: server rejects requests to `/mcp` with invalid bearer token (HTTP 401)
- [x] 11.4 Test: `/dashboard` remains accessible without authentication
- [x] 11.5 Test: API key auto-generation writes to `.env` and works for subsequent requests
- [ ] 11.6 Test: malicious tag names rejected by validation
- [ ] 11.7 Test: `/dashboard?days=abc` returns 200 with default period, not 500
- [x] 11.8 Test: error messages to clients don't contain file paths or internal details
