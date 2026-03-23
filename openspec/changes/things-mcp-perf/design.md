## Context

Things MCP is a 27-tool FastMCP 3.x server bridging AI assistants to Things 3 via AppleScript and the Things URL scheme. The full call chain for remote clients is: Claude → Hetzner (Caddy) → Tailscale → Mac → Python → osascript/URL scheme → Things. Each write operation incurs a mandatory 0.5–0.7s sleep (`url_scheme.py:111`) plus rate limiter overhead (`utils.py` RateLimiter at 30/min). Read operations go through the `things-py` library which queries Things' SQLite database, but `format_todo` then makes N+1 `things.get()` calls to resolve project/area titles.

An MCP tool review identified that a 24-item inbox triage session requires 25+ sequential MCP round-trips. The JSON URL scheme infrastructure (`construct_json_url`, `execute_json`, `build_todo_object`) already exists and supports N-item atomic creation in a single URL open — `plan-project` already uses this. AppleScript supports multi-item loops in a single subprocess call.

## Goals / Non-Goals

**Goals:**

- Establish performance baselines with a repeatable benchmark harness
- Reduce inbox triage from 25+ round-trips to ≤3 (1 read + 1 bulk action + optional follow-up)
- Fix N+1 query patterns in `format_todo` and `weekly-review` (immediate wins, no new tools)
- Add batch tools that collapse N write operations into 1 MCP call
- Improve tool ergonomics: title-based lookups, result limits, process-inbox `all` mode
- (Phase 3) Bypass things-py for reads with direct SQLite access for <100ms reads at scale

**Non-Goals:**

- Replacing things-py as a dependency (we use it for schema mapping, just bypass for hot paths)
- Adding Docker support (macOS-only constraint remains)
- Changing the transport layer (streamable-http stays)
- Real-time sync or push notifications from Things
- Changing the GTD methodology or tool naming conventions

## Decisions

### D1: Batch capture uses JSON URL scheme, not AppleScript

The Things JSON API (`things:///json?data=[...]`) accepts an array of to-do objects in a single URL open. `execute_json()` in `url_scheme.py` already implements this. One URL open = one 0.5s sleep regardless of item count.

**Alternative considered:** AppleScript loop creating N items. Rejected because the JSON API is purpose-built for this, already implemented, and avoids subprocess overhead entirely.

### D2: Batch complete/cancel uses single AppleScript with UUID loop

The Things URL scheme `update` action only accepts a single `id` — no array support. The JSON API only supports `add` (create), not `update` operations. Therefore bulk status changes must use AppleScript:

```applescript
tell application "Things3"
  repeat with tid in {"uuid1", "uuid2", "uuid3"}
    set status of (to do id tid) to completed
  end repeat
end tell
```

One subprocess call, one `run_applescript()` invocation, regardless of N.

**Alternative considered:** N parallel `asyncio.gather()` osascript subprocesses. Rejected because a single AppleScript with a loop is simpler, avoids process overhead, and eliminates partial-failure windows.

### D3: `bulk-triage` is a high-level composite tool

Rather than making the LLM chain `process-inbox(all=True)` → manual reasoning → separate bulk calls, `bulk-triage` accepts an array of `{task_id, action, ...}` decisions. Internally it groups by action type:

- `complete`/`cancel` → single AppleScript loop (D2)
- `defer`/`schedule`/`delegate` → URL scheme `update` calls (batched where possible)
- `project` → `convert-to-project` per item (cannot batch)

This is the highest-value tool: 20-item inbox goes from 40 MCP round-trips to 1 MCP call. Complete/cancel actions are O(1) subprocess; defer/schedule/delegate remain O(N) URL opens with individual sleeps but eliminate the MCP round-trip overhead per item.

### D4: `bulk-modify` supports uniform changes only

All tasks get the same modification (e.g., "move all to project X", "add tag @computer"). Per-task modifications would require a complex nested schema that's hard for LLMs to construct correctly. The LLM can call `modify-task` individually for divergent changes.

**Shape:**

```python
bulk_modify(task_ids: list[str], when=None, add_tags=None, project=None, area=None)
```

### D5: Error reporting is best-effort with per-item status

Things URL scheme writes are fire-and-forget (no acknowledgment). Batch tools:

1. Pre-fetch task titles before executing (for the return message)
2. Execute the batch
3. Report success count and any identified failures
4. On partial AppleScript failure, report which items were processed before failure

### D6: `format_todo` N+1 fix uses existing things-py dict fields

The `things-py` library returns `project_title` and `area_title` directly on the todo dict for most query paths. `format_todo` currently ignores these and calls `things.get(uuid)` for each. Fix: check for `project_title`/`area_title` first, fall back to `things.get()` only when absent. Zero-risk, high-impact.

### D7: `weekly-review` N+1 fix uses single query + group-by

Replace the per-project `things.todos(project=uuid, status="incomplete")` loop (N queries for N projects) with one `things.todos(status="incomplete")` call followed by Python `defaultdict` group-by on `project` UUID. Same result, 1 query instead of N.

### D8: `merge-areas` uses single AppleScript block

Replace the per-item `run_applescript()` loop with a single AppleScript that builds UUID lists and iterates internally. Reduces O(N) subprocess calls to O(1).

### D9: Benchmark harness is a standalone CLI, not test suite

`scripts/benchmark.py` runs against the live server (local or remote). It's a measurement tool, not a test. Outputs Markdown + JSON. Runs 5 iterations per operation, reports min/avg/p95/max. Can be re-run after each phase to validate improvements.

### D10: Phase 3 SQLite read layer uses things-py schema knowledge

Rather than reverse-engineering the schema, we study `things-py`'s query implementation and replicate the key queries with a direct `sqlite3` connection in read-only WAL mode. This gives us prepared statements, proper connection pooling, and the ability to do `GROUP BY` queries (eliminating N+1 at the database level). Fallback to `things-py` if the SQLite file is locked or the schema version is unrecognized.

## Risks / Trade-offs

**[Things JSON API only supports `add`, not `update`]** → Batch complete/cancel must use AppleScript. This is well-understood and the AppleScript loop approach is proven.

**[AppleScript loop partial failure]** → If AppleScript fails mid-loop, some items are processed and others aren't. Mitigated by pre-fetching titles and reporting partial progress. The `merge-areas` tool already handles this pattern.

**[SQLite schema is undocumented]** → May break on Things app updates. Mitigated by schema version check on startup, graceful fallback to things-py, and pinning to known schema versions.

**[`process-inbox(all=True)` changes GTD orthodoxy]** → GTD prescribes one-at-a-time processing. The `all` param is opt-in and the default behavior is unchanged. The GTD decision tree guidance is still returned per-item in the response.

**[Rate limiter interaction with batch tools]** → The rate limiter (30/min) applies per `execute_url` call. Batch tools that use a single URL open or single AppleScript naturally bypass this. The rate limiter protects against runaway individual calls, which is still correct.

**[Adding 5 new tools increases tool surface]** → From 27 to 32 tools. The GTD framing and tool annotations keep the surface navigable. The batch tools are clearly named (`bulk-*`) and documented as "use instead of N individual calls".

## Implementation Order

1. **Quick wins (no new tools):** format_todo N+1 fix, weekly-review N+1 fix, merge-areas AppleScript rewrite, validate_tool_registration cleanup
2. **Benchmark harness:** scripts/benchmark.py — establishes baselines before batch tools
3. **Batch tools:** bulk-capture → bulk-complete → bulk-cancel → bulk-modify → bulk-triage (in `tools_batch.py`)
4. **Tool ergonomics:** process-inbox `all` param, capture-task `when` param, task_title fallbacks, get-tasks `limit`, search-tasks docs
5. **SQLite read layer:** sqlite_reader.py, migrate read tools (separate change if scope grows)
