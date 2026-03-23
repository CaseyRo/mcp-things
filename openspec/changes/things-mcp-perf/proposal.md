## Why

Interactive GTD sessions are slow. Triaging a 24-item inbox requires 25+ sequential MCP round-trips, each spawning `osascript` with a mandatory 0.5–0.7s sleep. The full chain (Claude → Hetzner/Caddy → Tailscale → Mac → Python → osascript → Apple Events → Things) amplifies per-call latency. There is no instrumentation to quantify bottlenecks, read operations go through AppleScript when a direct SQLite path exists, and several tools have N+1 query patterns that compound under load. (Linear: CDI-708, CDI-709, CDI-710, CDI-711)

## What Changes

### Phase 0 — Benchmark Harness

- New `benchmark.py` CLI measuring end-to-end tool call latency, osascript duration, network round-trip, and task count scaling (10/50/100/200+)
- Cold vs. warm call profiling; output as Markdown report + structured JSON
- FastMCP middleware timing instrumentation

### Phase 1 — Batch Tools & Round-Trip Reduction

- **New tools:** `bulk-capture`, `bulk-complete`, `bulk-cancel`, `bulk-modify`, `bulk-triage`
- `bulk-capture`: uses existing `execute_json` (Things JSON URL scheme) — N items in 1 URL open
- `bulk-complete`/`bulk-cancel`: single AppleScript block with UUID loop (1 subprocess, not N)
- `bulk-modify`: uniform modification (same change to N tasks) via single AppleScript
- `bulk-triage`: highest-value tool — LLM submits all inbox decisions in 1 call (action per item: complete/cancel/defer/delegate/schedule/project)
- `process-inbox` gets optional `all: bool = False` param to return full inbox for automated triage
- `merge-areas` rewritten to use single AppleScript block instead of per-item subprocess loop

### Phase 1b — Tool Ergonomics

- Add `task_title` fallback to `defer-task`, `delegate-task`, `modify-task` (matching `complete-task` pattern)
- Add `limit` param to `get-tasks` (default 50, max 200)
- Document existing 20-item cap in `search-tasks`, make configurable
- Add optional `when` param to `capture-task` to avoid capture-then-schedule two-step

### Phase 2 — Performance Fixes (Pre-SQLite)

- Fix `format_todo` N+1: use `project_title`/`area_title` from things-py dict before falling back to `things.get()`
- Fix `weekly-review` N+1: replace per-project `things.todos(project=uuid)` with single `things.todos(status="incomplete")` + Python group-by
- Clean up stale `validate_tool_registration` in utils.py

### Phase 3 — SQLite Read Layer

- Direct SQLite reads for all read tools, bypassing AppleScript entirely
- Database: `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingssqlite`
- Read-only connection (`?mode=ro`, WAL-compatible); writes stay on AppleScript/URL scheme
- Schema version check on startup with warning log for unknown versions
- Graceful fallback to things-py if SQLite file is locked or missing

## Capabilities

### New Capabilities

- `benchmark-harness`: CLI tool and middleware for measuring server performance (latency, scaling, cold/warm)
- `batch-tools`: Compound tools accepting arrays to collapse N round-trips into 1 (bulk-capture, bulk-complete, bulk-cancel, bulk-modify, bulk-triage)
- `sqlite-read-layer`: Direct SQLite database reads bypassing AppleScript for all read operations

### Modified Capabilities

- `server-testing`: Benchmark harness adds new test fixtures and measurement infrastructure

## Impact

**Code changes:**

- New files: `benchmark.py`, `tools_batch.py`, `sqlite_reader.py`
- Modified: `tools_gtd_core.py` (process-inbox all param, capture-task when param), `tools_gtd_organize.py` (merge-areas rewrite, task_title fallbacks), `tools_utility.py` (limit params, search-tasks docs), `formatters.py` (N+1 fix), `tools_gtd_reflect.py` (weekly-review N+1 fix), `utils.py` (cleanup)
- Modified: `tool_annotations.py` (annotations for new batch tools)

**APIs:** 5 new MCP tools added; 6 existing tools get new optional parameters (backward-compatible)

**Dependencies:** No new external dependencies. SQLite read layer uses stdlib `sqlite3`.

**Risk:** SQLite schema is undocumented and may change across Things app updates. Mitigated by schema validation on startup and fallback to things-py.
