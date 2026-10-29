# Architecture

## The short version

```
Reads:   MCP client → FastMCP → things.py → Things SQLite database → cache → response
Writes:  MCP client → FastMCP → URL builder → open -g things:///… → Things app
                                           → read-back from SQLite → real thing_id
```

Things has no public API. It has a database it keeps on disk, a URL scheme
that accepts commands, and an AppleScript dictionary. mcp-things uses each for
what it does best.

## Reads

Read tools use [things.py](https://github.com/thingsapi/things.py), which
queries the Things SQLite database directly. That is fast and needs no running
UI. Results are cached with a TTL per list (30 s for Inbox and Today, up to
10 minutes for areas and tags, see `CACHE_TTL` in `cache.py`), and every write
invalidates the caches it affects.

List views (`get-tasks`, `search-tasks`) leave checklists empty for speed.
Detail views (`get-project`, `focus-mode`, single-item `process-inbox`) load
them.

## Writes

Write tools build a Things URL (`things:///add`, `things:///update`,
`things:///json` for projects with tasks) and open it with `open -g`, so Things
stays in the background. The URL scheme returns nothing, which shapes the rest:

- **Settle time.** After opening a URL the server waits 0.5 to 0.7 seconds for Things to apply it.
- **Read-back.** Create tools then poll the database for a to-do with the exact title, created
  after the call started (0.25 s steps, about 3.5 s in total). Found: the response carries the
  real `thing_id`. Not found yet: `thing_id` is `null`, which means "not yet confirmed", never
  "failed".
- **Tags.** Missing tags are created first (`tag_handler.py`), because the URL scheme silently
  drops unknown tags.
- **AppleScript** covers what the URL scheme cannot, mainly area operations.
- **Repeats.** Things offers no way to create a repeat rule from outside the app, so the server
  keeps the rule in the to-do's notes and a sweep every 10 minutes creates the next occurrence
  (`repeat.py`).

Reliability helpers in `utils.py`: retries (`RETRY_ATTEMPTS`, `RETRY_DELAY`), a
circuit breaker that opens after 5 consecutive failures for 60 seconds, and a
rate limiter.

## Why not Docker

AppleScript and the URL scheme only work inside a logged-in macOS session with
Things installed, and the macOS Automation grant is tied to the interpreter
that runs the server. A container has neither, so the server runs as a native
process, usually under launchd.

## The MCP layer

- **Transport:** streamable HTTP at `/mcp`, stateless. SSE was removed.
- **Auth:** a bearer key checked with `hmac.compare_digest` (`auth.py`). Health endpoints are open.
- **Client compatibility** (`server_core.py`, `ClientCompatibilityMiddleware`):
  - flattens `anyOf` into type arrays for every client (n8n needs it);
  - applies strict-mode schemas for ChatGPT (`additionalProperties: false`, every field required and nullable);
  - strips the extra arguments and explicit nulls n8n sends.
  The same transforms apply to input and output schemas.
- **Responses:** every tool returns a text block plus a typed `structuredContent` envelope
  (`tool_results.py`, `models.py`). Failures raise `ToolError`.
- **Telemetry:** one JSON line per tool call on stderr with tool name, duration and outcome.
  Arguments and results are never logged, and log redaction keeps task titles and notes out
  of every log.

## Source map

```
src/things_mcp/
├── fast_server.py        # Entry point: creates the server, registers tools, health routes
├── server_core.py        # Server factory, client middleware, schema transforms
├── client_compat.py      # Accept-header patches, transport middleware
├── auth.py               # Bearer token verification
├── tools_gtd_core.py     # Engage, Capture, Clarify
├── tools_gtd_organize.py # Organize
├── tools_gtd_reflect.py  # Reflect
├── tools_utility.py      # Search, lists, cache stats, triage insights
├── tools_batch.py        # bulk-* tools
├── tool_results.py       # make_result / write_result / bulk_result envelopes
├── models.py             # Typed payloads
├── reader.py             # SQLite reads, read-back after creates
├── url_scheme.py         # Things URL builders and execution
├── applescript_bridge.py # AppleScript execution
├── repeat.py             # Server-side repeat rules and sweep
├── resolvers.py          # Name-to-UUID resolution
├── triage_tracker.py     # Triage history and trends
├── cache.py              # @cached decorator, TTLs
├── utils.py              # Circuit breaker, rate limiter
├── tag_handler.py        # Creates missing tags
├── input_validation.py   # Tag names, UUIDs, lengths
├── formatters.py         # Text output
├── logging_config.py     # Structured logging with redaction
├── usage.py              # Usage telemetry (vendored)
└── config.py             # Settings
```
