"""Unit tests for the write overlay — read-your-writes consistency (CDI-1255).

These tests exercise the in-process overlay and its integration with the
``reader`` merge layer without touching Things 3 or the SQLite store.
"""

import time

import pytest

from things_mcp.write_overlay import (
    OVERLAY_ID_PREFIX,
    WriteOverlay,
    is_overlay_id,
)

pytestmark = [pytest.mark.unit]


class TestOverlayRecording:
    def test_record_returns_synthetic_id(self):
        ov = WriteOverlay()
        oid = ov.record("Buy milk")
        assert is_overlay_id(oid)
        assert oid.startswith(OVERLAY_ID_PREFIX)

    def test_recorded_item_is_visible(self):
        ov = WriteOverlay()
        ov.record("SMOKE-TEST-thing", tags=["@errands"], notes="2L")
        rows = ov.overlay_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["title"] == "SMOKE-TEST-thing"
        assert row["status"] == "incomplete"
        assert row["_overlay"] is True
        assert row["tags"] == ["@errands"]

    def test_record_requires_title(self):
        ov = WriteOverlay()
        with pytest.raises(ValueError):
            ov.record("")

    def test_when_someday_sets_start(self):
        ov = WriteOverlay()
        ov.record("Later thing", when="someday")
        assert ov.overlay_rows()[0]["start"] == "Someday"

    def test_when_today_sets_anytime_bucket(self):
        ov = WriteOverlay()
        ov.record("Scheduled thing", when="today")
        assert ov.overlay_rows()[0]["start"] == "Anytime"


class TestOverlayQuerying:
    def test_query_substring_match(self):
        ov = WriteOverlay()
        ov.record("Call the dentist")
        ov.record("Email the lawyer")
        rows = ov.overlay_rows(query="dentist")
        assert len(rows) == 1
        assert rows[0]["title"] == "Call the dentist"

    def test_query_matches_notes(self):
        ov = WriteOverlay()
        ov.record("Errand", notes="pick up prescription")
        assert len(ov.overlay_rows(query="prescription")) == 1

    def test_query_no_match(self):
        ov = WriteOverlay()
        ov.record("Call the dentist")
        assert ov.overlay_rows(query="zzz-nonexistent") == []

    def test_completed_status_never_matches_overlay(self):
        ov = WriteOverlay()
        ov.record("Fresh task")
        assert ov.overlay_rows(status="completed") == []
        assert ov.overlay_rows(status="canceled") == []
        # incomplete and None do match
        assert len(ov.overlay_rows(status="incomplete")) == 1
        assert len(ov.overlay_rows(status=None)) == 1


class TestOverlayTTL:
    def test_entries_expire(self):
        ov = WriteOverlay(ttl_seconds=0)
        ov.record("Ephemeral")
        # ttl=0 -> any elapsed time expires it
        time.sleep(0.01)
        assert ov.overlay_rows() == []
        assert ov.has_recent_writes() is False

    def test_live_within_ttl(self):
        ov = WriteOverlay(ttl_seconds=60)
        ov.record("Still here")
        assert ov.has_recent_writes() is True
        assert len(ov.overlay_rows()) == 1


class TestMergeIntoReadResult:
    def test_merge_appends_provisional_item(self):
        ov = WriteOverlay()
        ov.record("New captured task")
        persisted = [{"uuid": "real-1", "title": "Existing task"}]
        merged = ov.merge_into(persisted, status="incomplete")
        titles = [r["title"] for r in merged]
        assert "Existing task" in titles
        assert "New captured task" in titles
        assert len(merged) == 2

    def test_merge_dedupes_once_persisted(self):
        """Once SQLite has the real row, the overlay row is suppressed."""
        ov = WriteOverlay()
        ov.record("Buy milk")
        # Simulate Things having flushed the item to SQLite under a real UUID.
        persisted = [{"uuid": "real-xyz", "title": "Buy milk"}]
        merged = ov.merge_into(persisted, status="incomplete")
        assert len(merged) == 1
        assert merged[0]["uuid"] == "real-xyz"  # real row wins, no duplicate

    def test_merge_dedupe_is_case_insensitive(self):
        ov = WriteOverlay()
        ov.record("Buy Milk")
        persisted = [{"uuid": "real-1", "title": "buy milk"}]
        merged = ov.merge_into(persisted, status="incomplete")
        assert len(merged) == 1

    def test_merge_respects_query_filter(self):
        ov = WriteOverlay()
        ov.record("Call the dentist")
        merged = ov.merge_into([], query="lawyer", status="incomplete")
        assert merged == []

    def test_merge_noop_when_empty_overlay(self):
        ov = WriteOverlay()
        persisted = [{"uuid": "real-1", "title": "Existing"}]
        merged = ov.merge_into(persisted, status="incomplete")
        assert merged == persisted


class TestStalenessSignalling:
    def test_no_writes_not_stale(self):
        ov = WriteOverlay()
        assert ov.is_index_stale() is False

    def test_recent_write_with_unflushed_db_is_stale(self, monkeypatch):
        ov = WriteOverlay()
        # DB mtime frozen in the past; the write records that past mtime, and a
        # subsequent read sees the DB mtime has not advanced -> stale.
        monkeypatch.setattr("things_mcp.write_overlay._safe_db_mtime", lambda: 1000.0)
        ov.record("Just written")
        assert ov.is_index_stale() is True

    def test_db_caught_up_not_stale(self, monkeypatch):
        ov = WriteOverlay()
        # At write time the DB mtime was 1000; by read time it advanced to 2000,
        # meaning Things flushed -> not stale.
        mtimes = iter([1000.0, 2000.0, 2000.0, 2000.0])
        monkeypatch.setattr(
            "things_mcp.write_overlay._safe_db_mtime", lambda: next(mtimes)
        )
        ov.record("Written then flushed")
        assert ov.is_index_stale() is False

    def test_unknown_db_mtime_is_conservatively_stale(self, monkeypatch):
        ov = WriteOverlay()
        monkeypatch.setattr("things_mcp.write_overlay._safe_db_mtime", lambda: None)
        ov.record("Can't read db mtime")
        assert ov.is_index_stale() is True
