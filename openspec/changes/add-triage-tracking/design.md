# Design: Add Triage Tracking & Insights

## Key Decision: Why JSON over SQLite

At our expected data volume (5-20 items/day, 90-day window = 450-1800 records), JSON is simpler and sufficient. The `_load()` / `_save()` abstraction means we can swap to SQLite later without changing the public API.

## Record Schema

```python
{
    "record_id": "uuid4",
    "timestamp": "2026-03-10T14:30:00Z",  # ISO 8601
    "task_id": "Things UUID",
    "task_title": "OpenSEO",
    "task_notes": "https://github.com/...",  # first 200 chars only
    "task_tags": ["@computer"],
    "action": "completed",  # enum: completed, canceled, deferred-someday, deferred-date, delegated, modified, converted-to-project
    "action_details": {},  # varies by action
    "category": "repo-research",
    "category_confidence": 0.9,
    "source": "process-inbox"  # or "direct"
}
```

## Categorization Architecture

```
categorize_task(title, notes, tags) -> (category: str, confidence: float)
```

Designed as a pure function with no side effects. This makes it trivial to:

1. Unit test each rule independently
2. Replace with LLM call later (same signature)
3. A/B test heuristics vs LLM accuracy

Rules are evaluated in priority order (first match wins). Each rule is a tuple of `(condition_fn, category, confidence)` — easy to add/remove/reorder.

## Source Detection

Problem: MCP tools are stateless — `process-inbox` and `complete-task` are separate calls with no shared session state.

Solution: The tracker stores `last_inbox_view_timestamp`. When `record()` is called, if the last inbox view was within 60 seconds, the source is `"process-inbox"`. This is a heuristic but works well in practice because:

- Triage sessions process items sequentially
- The gap between viewing an item and acting on it is typically <30s
- False positives (coincidental timing) are harmless for trend analysis

## Weekly Review Integration

The triage section is appended at the end of existing weekly review output. Format:

```
## Triage Activity This Week

**14 items triaged**

Actions taken:
- completed: 6
- scheduled: 4
- canceled: 3
- deferred: 1

Item categories:
- repo-research: 5
- vague-capture: 4
- client-person: 3
- general: 2

Tip: 29% of captures were vague. Try adding notes when capturing.
```

## Triage Insights Tool Output

Provides more detail than the weekly review section:

```
Triage Insights (last 7 days)

Total: 14 items | Avg: 2.0/day | Busiest: Monday (5)

Actions:
  completed  ██████░░░░  6 (43%)
  scheduled  ████░░░░░░  4 (29%)
  canceled   ███░░░░░░░  3 (21%)
  deferred   █░░░░░░░░░  1 (7%)

Categories:
  repo-research  █████░░░░░  5 (36%)
  vague-capture  ████░░░░░░  4 (29%)
  client-person  ███░░░░░░░  3 (21%)
  general        ██░░░░░░░░  2 (14%)
```

With `show_trends=True`:

```
Weekly Trends (4 weeks):
  Week of Mar 3:  14 items (↑ from 8)
  Week of Feb 24:  8 items (↓ from 12)
  Week of Feb 17: 12 items (↑ from 10)
  Week of Feb 10: 10 items
```

## Error Handling

All `triage_tracker.record()` calls are wrapped:

```python
try:
    triage_tracker.record(...)
except Exception:
    logger.debug("Triage tracking failed (non-critical)")
```

Tracking is best-effort. A corrupt JSON file, disk full, or permission error should never break task management operations.

## Future Upgrade Path

### LLM Categorization

Replace `categorize_task()` body with an LLM call. The function signature stays the same. Could gate behind an env var:

```
THINGS_MCP_TRIAGE_LLM=true  # opt-in to LLM categorization
```

### SQLite Storage

Replace `_load()` / `_save()` with SQLite operations. The `TriageTracker` public API stays the same. Would enable:

- Rolling averages without loading all records
- Time-bucket queries (busiest hour of day)
- Category-over-time trend lines

### Export

Add a `triage-export` tool that dumps records as CSV or JSON for external analysis.
