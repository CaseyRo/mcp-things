# Troubleshooting

Find your symptom, then the cause and the fix. If nothing here helps, please
[open an issue](https://github.com/CaseyRo/mcp-things/issues/new/choose) and
include the log described at the end.

## Write tools report success but nothing appears in Things

- **Things URLs are off, or the token is missing.** Check Things → Settings → General →
  Enable Things URLs, and that `THINGS_AUTH_TOKEN` in `.env` matches the token shown there.
  Re-run `uv run python scripts/configure_token.py` if in doubt.
- **Things was not running.** The server starts it and waits two seconds, which can be too
  short on a cold start. Try again once Things is open.

## `thing_id` is `null` after a create

Not an error. The URL scheme returns no ID, so the server looks the new to-do up
in the database for about 3.5 seconds. If Things commits later than that, the
create still happened; `search-tasks` will find it.

## A tool call hangs

macOS ties the Automation permission for Things to the exact Python binary
that runs the server. If you recreated `.venv` with a different Python (for
example after `uv` picked a newer one), AppleScript waits for a permission
prompt nobody sees.

- Run the server once in a terminal and accept the Automation prompt, or
- check System Settings → Privacy & Security → Automation for the new interpreter, or
- go back to the previous interpreter: pin it in `.python-version`, `uv sync --locked`, restart.

## 401 Unauthorized

The client is not sending `Authorization: Bearer <THINGS_MCP_API_KEY>`, or the
key changed. The current key is in `.env`; the server prints it on startup.

## The client can't list or call tools

- **n8n:** see [clients/n8n.md](clients/n8n.md). The server already strips n8n's extra
  arguments and nulls; schema errors usually mean an old n8n version.
- **ChatGPT:** see [clients/chatgpt.md](clients/chatgpt.md). Strict-mode schemas are applied
  automatically when the client identifies as ChatGPT.
- **Claude Desktop without `url` support:** use the `mcp-remote` bridge from
  [setup.md](setup.md#claude-desktop).

## Writes start failing in a row

After 5 consecutive failures the circuit breaker opens for 60 seconds and
writes fail fast. Look for the first error in the log; it is usually Things
not running or a permission problem.

## Misleading log lines

- `ERROR Failed to ensure tags exist` appears on successful calls: the tag check treats an
  empty AppleScript result as a failure. Ignore it unless tags are actually missing.
- After updating the server, a client session that was open before the restart can reject
  results with "Structured content does not match the tool's output schema". Reconnect the
  client so it fetches the current schemas.

## A repeating to-do didn't come back

The sweep runs every 10 minutes and only for completed to-dos whose notes still
contain the `🔁 repeat:` line. Canceling an occurrence ends the series.

## Collecting a log for an issue

```bash
curl -s http://127.0.0.1:8009/health      # is it up?
tail -n 50 /path/to/your/stderr.log       # under launchd: the StandardErrorPath file
```

Tool-call lines contain the tool name, duration and outcome, never your task
content, so they are safe to paste. Do remove your API key and Things token if
they appear anywhere. Set `THINGS_MCP_DEBUG=true` for more detail.
