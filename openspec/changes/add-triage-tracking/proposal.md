# Change: Add Triage Tracking & Insights

**Status: IMPLEMENTED** (2026-03-10)

## Agent Review Findings (incorporated)

- **Legal:** Don't store PII. Store only derived fields (category, action, timestamp). Done.
- **Security:** File permissions 0600, atomic writes, lock around load+modify+save. Done.
- **UX:** Track sessions not just actions, surface insights at inbox-zero, plain language over charts. Done.
- **UI:** GTD Health Dashboard with Cultured Code aesthetic and shadcn token system. Done.

## Why

During inbox triage sessions, we process 10-20+ items but lose all signal about patterns. Common questions we can't answer today:

- What percentage of inbox captures are vague (no notes, no context)?
- What's the most common action taken? (complete vs defer vs cancel)
- Are we capturing mostly GitHub repos? Client work? Random ideas?
- Is our capture quality improving over time?
- How does our triage behavior change week-to-week?

This data would improve both the **user's GTD practice** (via `weekly-review` insights) and the **MCP server itself** (by showing which tools are underused, what workflows are missing).

## Design Options

### Option A: JSON File Tracker (Recommended)

**Storage:** Append-only JSON file at `~/.things-mcp/triage_history.json` (follows existing DLQ pattern).

**How it works:**

- After each triage action (complete, cancel, defer, schedule, delegate, modify), record a structured event
- Categorize items using heuristic rules (no LLM, no network)
- Surface trends via enhanced `weekly-review` and new `triage-insights` tool
- Auto-rotate records older than 90 days

**Pros:**

- Zero dependencies, no network, no LLM costs
- Follows existing `~/.things-mcp/` data directory pattern
- Simple to implement (~200 lines new code)
- Works offline, privacy-preserving

**Cons:**

- Heuristic categorization is ~80% accurate (no semantic understanding)
- JSON file doesn't scale past thousands of records (but 90-day rotation handles this)
- No cross-device sync

### Option B: SQLite Tracker

**Storage:** SQLite database at `~/.things-mcp/triage_history.db`

**How it works:** Same recording logic as Option A, but uses SQLite for storage. Enables SQL queries for complex trend analysis.

**Pros:**

- Better query performance for large datasets
- Can do complex aggregations (busiest hour, rolling averages)
- Atomic writes, no file corruption risk
- things-py already uses SQLite, so the pattern is familiar

**Cons:**

- Adds complexity for marginal gain at our data volume
- Harder to inspect/debug than a JSON file
- SQLite is overkill for <2000 records per 90-day window

### Option C: Optional LLM Categorization

**Storage:** Either JSON or SQLite (orthogonal choice)

**How it works:** Before recording, optionally call a local/remote LLM to classify the task into a richer category taxonomy. Falls back to heuristics if no LLM is configured.

**Pros:**

- Much better categorization accuracy (95%+)
- Can detect nuanced categories ("client follow-up" vs "client deliverable")
- Could generate natural language insights ("You've been deferring health tasks for 3 weeks")

**Cons:**

- Adds latency to every triage action (100-500ms for local, 1-2s for remote)
- Requires LLM configuration (API key or local model)
- Increases complexity significantly
- Privacy concern: task titles/notes sent to LLM
- Overkill for MVP — can always add later

### Option D: Track in Things 3 Itself

**How it works:** Instead of a separate data store, use Things tags and notes to track triage metadata. Add a `triaged` tag, append triage timestamp to notes.

**Pros:**

- No separate data store
- Data lives with the task (portable)
- Visible in Things app UI

**Cons:**

- Pollutes task data with tracking metadata
- Can't query completed/canceled tasks easily (logbook access is limited)
- No aggregation capability
- Doesn't survive task deletion
- Fundamentally wrong abstraction — triage history is about the *process*, not the *task*

## Recommendation

**Option A (JSON File Tracker)** for MVP, with the architecture designed so Option B (SQLite) or Option C (LLM) can be swapped in later without changing the recording API or the insight tools.

Specifically:

- `TriageTracker` class with `record()` / `get_summary()` / `get_trends()` interface
- `categorize_task()` as a standalone function (easy to replace with LLM later)
- Storage backend behind `_load()` / `_save()` methods (swap JSON for SQLite later)

## What Changes

### New module: `triage_tracker.py`

Core tracking module with:

- **`TriageRecord`** — structured record: timestamp, task_id, action, category, category_confidence, source (inbox vs direct)
- **`TriageTracker`** — singleton that records events, queries history, generates summaries
- **`categorize_task(title, notes, tags)`** — heuristic classifier returning (category, confidence)

**Heuristic categories (priority order):**

| Condition | Category | Confidence |
|-----------|----------|------------|
| GitHub/GitLab URL in title or notes | `repo-research` | 0.9 |
| Any URL in title or notes | `web-reference` | 0.85 |
| Title matches "Name: ..." or "Name - ..." pattern | `client-person` | 0.7 |
| Has `waiting-for` tag | `delegation` | 0.9 |
| Title contains review/check/follow up | `follow-up` | 0.7 |
| Title contains buy/order/purchase | `purchase` | 0.75 |
| No notes AND title < 30 chars | `vague-capture` | 0.6 |
| Default | `general` | 0.5 |

**Inbox source detection:** Track `process-inbox` call timestamps. If a triage action happens within 60s of an inbox view, mark source as `"process-inbox"` instead of `"direct"`.

### Enhanced tool: `weekly-review`

Append a "Triage Activity" section showing:

- Total items triaged this week
- Action breakdown (completed, canceled, deferred, etc.)
- Top categories
- Vague capture warning if >30% of items have no context

### New tool: `triage-insights`

Dedicated analytics tool with parameters:

- `days` (default 7) — analysis window
- `category` / `action` — filters
- `show_trends` (bool) — week-over-week comparison

Returns: action frequency, category breakdown, daily volume, busiest day, and trend arrows.

### Recording integration

Add `triage_tracker.record()` calls to:

- `complete-task` — action: "completed"
- `modify-task` (when canceled=True) — action: "canceled"
- `modify-task` (when/project/area changes) — action: "modified"
- `defer-task` — action: "deferred-someday" or "deferred-date"
- `delegate-task` — action: "delegated"
- `convert-to-project` — action: "converted-to-project"
- `process-inbox` — records inbox view timestamp (for source detection)

All recording is wrapped in try/except — tracking failures never break tool operations.

### Privacy

- Triage history file is local only (`~/.things-mcp/`)
- Task titles stored in records (needed for categorization) but never logged
- 90-day auto-rotation keeps file bounded
- No network calls for categorization (heuristics only)

## Impact

- **New files**: `src/things_mcp/triage_tracker.py`, `tests/test_triage_tracker.py`
- **Modified files**: `tools_gtd_core.py`, `tools_gtd_organize.py`, `tools_gtd_reflect.py`, `tools_utility.py`, `tool_annotations.py`
- **Tool count**: 20 → 21 (adds `triage-insights`)
- **Dependencies**: None (stdlib only)
- **Risk**: Low — all tracking is additive, wrapped in try/except, no existing behavior changes
