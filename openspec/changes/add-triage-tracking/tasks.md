# Tasks: Add Triage Tracking & Insights

## Implementation Checklist

### Phase 1: Core Tracker

- [ ] Create `src/things_mcp/triage_tracker.py` with `TriageTracker` class
- [ ] Implement `categorize_task()` heuristic classifier
- [ ] Implement JSON persistence with `_load()` / `_save()` and threading.Lock
- [ ] Implement 90-day auto-rotation in `_save()`
- [ ] Implement `record()`, `record_inbox_view()`, `get_summary()`, `get_trends()`
- [ ] Create `tests/test_triage_tracker.py` with unit tests (categorization, persistence, rotation, source detection)

### Phase 2: Recording Integration

- [ ] Add recording to `complete-task` in `tools_gtd_core.py`
- [ ] Add recording to `convert-to-project` in `tools_gtd_core.py`
- [ ] Add inbox view tracking to `process-inbox` in `tools_gtd_core.py`
- [ ] Add recording to `modify-task` in `tools_gtd_organize.py` (canceled + modified)
- [ ] Add recording to `defer-task` in `tools_gtd_organize.py`
- [ ] Add recording to `delegate-task` in `tools_gtd_organize.py`
- [ ] Fetch task data BEFORE update calls (needed for categorization after URL scheme changes)

### Phase 3: Insight Tools

- [ ] Add `triage-insights` annotation to `tool_annotations.py`
- [ ] Create `triage-insights` tool in `tools_utility.py`
- [ ] Enhance `weekly-review` in `tools_gtd_reflect.py` with triage summary section

### Phase 4: Documentation & Testing

- [ ] Update `CLAUDE.md` — tool count, architecture listing, new tool docs
- [ ] Run `ruff check .` and `ruff format .`
- [ ] Run full test suite (`pytest tests -m "not real"`)
- [ ] Manual triage test with server restart to verify end-to-end

## Testing Plan

- Unit tests for categorization heuristics (each category rule)
- Unit tests for JSON persistence (write, read, rotate)
- Unit tests for summary/trend calculations
- Unit tests for inbox source detection (within 60s → process-inbox)
- Integration test: record → get_summary round-trip
- All tests use `tmp_path` fixture (no production data touched)
