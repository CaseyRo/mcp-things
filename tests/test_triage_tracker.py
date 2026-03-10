"""Unit tests for the triage tracker module."""

import pytest

from things_mcp.triage_tracker import TriageTracker, categorize_task


# === Categorization Tests ===


class TestCategorizeTask:
    """Tests for the heuristic categorizer."""

    def test_github_url_in_notes(self):
        cat, conf = categorize_task("OpenSEO", notes="https://github.com/foo/bar")
        assert cat == "repo-research"
        assert conf == 0.9

    def test_github_url_in_title(self):
        cat, _ = categorize_task("Check github.com/foo/bar")
        assert cat == "repo-research"

    def test_gitlab_url(self):
        cat, _ = categorize_task("Review", notes="See https://gitlab.com/project")
        assert cat == "repo-research"

    def test_web_reference(self):
        cat, conf = categorize_task("Article", notes="https://example.com/article")
        assert cat == "web-reference"
        assert conf == 0.85

    def test_client_person_colon(self):
        cat, conf = categorize_task("Marcel: update website")
        assert cat == "client-person"
        assert conf == 0.7

    def test_client_person_dash(self):
        cat, _ = categorize_task("Alice - review proposal")
        assert cat == "client-person"

    def test_waiting_for_tag(self):
        cat, conf = categorize_task("Some task", tags=["waiting-for"])
        assert cat == "delegation"
        assert conf == 0.9

    def test_follow_up(self):
        cat, _ = categorize_task("Review the quarterly report")
        assert cat == "follow-up"

    def test_purchase(self):
        cat, _ = categorize_task("Buy new keyboard")
        assert cat == "purchase"

    def test_vague_capture_short_no_notes(self):
        cat, conf = categorize_task("Paperclip")
        assert cat == "vague-capture"
        assert conf == 0.6

    def test_not_vague_if_has_notes(self):
        cat, _ = categorize_task("Paperclip", notes="Check this out")
        assert cat != "vague-capture"

    def test_not_vague_if_long_title(self):
        cat, _ = categorize_task(
            "This is a really long task title that is very descriptive"
        )
        assert cat != "vague-capture"

    def test_general_default(self):
        cat, conf = categorize_task(
            "Refactor the authentication module", notes="Important for security"
        )
        assert cat == "general"
        assert conf == 0.5

    def test_priority_github_over_vague(self):
        """GitHub URL should win even with short title."""
        cat, _ = categorize_task("Test", notes="github.com/foo")
        assert cat == "repo-research"

    def test_empty_title(self):
        cat, _ = categorize_task("")
        assert cat == "vague-capture"

    def test_none_values(self):
        cat, _ = categorize_task("Test task", notes=None, tags=None)
        assert cat in (
            "vague-capture",
            "general",
            "follow-up",
            "purchase",
            "client-person",
        )


# === Tracker Tests ===


class TestTriageTracker:
    """Tests for the TriageTracker class."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a tracker with a temp file."""
        return TriageTracker(history_file=tmp_path / "triage_history.json")

    def test_record_and_retrieve(self, tracker):
        tracker.record(
            task_id="abc123",
            task_title="Test task",
            task_notes=None,
            task_tags=None,
            action="completed",
        )
        records = tracker.get_records(days=1)
        assert len(records) == 1
        assert records[0]["action"] == "completed"
        assert records[0]["task_id"] == "abc123"

    def test_no_title_in_record(self, tracker):
        """Verify task title is NOT persisted (privacy by design)."""
        tracker.record(
            task_id="abc123",
            task_title="Marcel: do stuff",
            task_notes="secret notes",
            task_tags=["private"],
            action="completed",
        )
        records = tracker.get_records(days=1)
        record = records[0]
        assert "task_title" not in record
        assert "task_notes" not in record
        assert "task_tags" not in record
        # But category should be derived from the title
        assert record["category"] == "client-person"

    def test_category_stored(self, tracker):
        tracker.record(
            task_id="abc123",
            task_title="OpenSEO",
            task_notes="https://github.com/foo/bar",
            action="completed",
        )
        records = tracker.get_records(days=1)
        assert records[0]["category"] == "repo-research"
        assert records[0]["category_confidence"] == 0.9

    def test_multiple_records(self, tracker):
        for i in range(5):
            tracker.record(
                task_id=f"task-{i}",
                task_title=f"Task {i}",
                action="completed",
            )
        records = tracker.get_records(days=1)
        assert len(records) == 5

    def test_filter_by_action(self, tracker):
        tracker.record(task_id="a", task_title="A", action="completed")
        tracker.record(task_id="b", task_title="B", action="canceled")
        tracker.record(task_id="c", task_title="C", action="completed")

        completed = tracker.get_records(days=1, action="completed")
        assert len(completed) == 2

        canceled = tracker.get_records(days=1, action="canceled")
        assert len(canceled) == 1

    def test_filter_by_category(self, tracker):
        tracker.record(
            task_id="a",
            task_title="Cmux",
            task_notes="https://github.com/foo",
            action="completed",
        )
        tracker.record(task_id="b", task_title="Stuff", action="completed")

        repos = tracker.get_records(days=1, category="repo-research")
        assert len(repos) == 1

    def test_summary(self, tracker):
        tracker.record(task_id="a", task_title="A", action="completed")
        tracker.record(task_id="b", task_title="B", action="canceled")
        tracker.record(task_id="c", task_title="C", action="completed")

        summary = tracker.get_summary(days=7)
        assert summary["total"] == 3
        assert summary["actions"]["completed"] == 2
        assert summary["actions"]["canceled"] == 1

    def test_summary_empty(self, tracker):
        summary = tracker.get_summary(days=7)
        assert summary["total"] == 0

    def test_inbox_source_detection(self, tracker):
        """Records within 60s of inbox view should be marked as process-inbox."""
        tracker.record_inbox_view()
        tracker.record(task_id="a", task_title="A", action="completed")

        records = tracker.get_records(days=1)
        assert records[0]["source"] == "process-inbox"

    def test_direct_source_without_inbox_view(self, tracker):
        """Records without recent inbox view should be marked as direct."""
        tracker.record(task_id="a", task_title="A", action="completed")

        records = tracker.get_records(days=1)
        assert records[0]["source"] == "direct"

    def test_session_tracking(self, tracker):
        tracker.record_inbox_view()
        tracker.record(task_id="a", task_title="A", action="completed")
        tracker.record(task_id="b", task_title="B", action="canceled")

        records = tracker.get_records(days=1)
        # Both should have same session_id
        assert records[0]["session_id"] == records[1]["session_id"]
        assert records[0]["session_id"] is not None

    def test_file_persistence(self, tmp_path):
        """Records should persist across tracker instances."""
        file = tmp_path / "triage_history.json"

        tracker1 = TriageTracker(history_file=file)
        tracker1.record(task_id="a", task_title="A", action="completed")

        tracker2 = TriageTracker(history_file=file)
        records = tracker2.get_records(days=1)
        assert len(records) == 1

    def test_file_permissions(self, tmp_path):
        """File should be created with 0600 permissions."""
        file = tmp_path / "triage_history.json"
        tracker = TriageTracker(history_file=file)
        tracker.record(task_id="a", task_title="A", action="completed")

        assert file.exists()
        mode = file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_purge_all(self, tracker):
        tracker.record(task_id="a", task_title="A", action="completed")
        tracker.record(task_id="b", task_title="B", action="canceled")

        deleted = tracker.purge()
        assert deleted == 2
        assert tracker.get_records(days=0) == []

    def test_purge_by_task_id(self, tracker):
        tracker.record(task_id="a", task_title="A", action="completed")
        tracker.record(task_id="b", task_title="B", action="canceled")

        deleted = tracker.purge(task_id="a")
        assert deleted == 1
        records = tracker.get_records(days=0)
        assert len(records) == 1
        assert records[0]["task_id"] == "b"

    def test_corrupt_file_handled(self, tmp_path):
        """Corrupt JSON file should not crash the tracker."""
        file = tmp_path / "triage_history.json"
        file.write_text("not valid json{{{")

        tracker = TriageTracker(history_file=file)
        records = tracker.get_records(days=1)
        assert records == []

        # Should still be able to write
        tracker.record(task_id="a", task_title="A", action="completed")
        assert len(tracker.get_records(days=1)) == 1

    def test_trends(self, tracker):
        trends = tracker.get_trends(weeks=4)
        # Empty tracker should return empty trends
        assert isinstance(trends, list)

    def test_no_context_cancel_rate(self, tracker):
        # Cancel with vague capture
        tracker.record(task_id="a", task_title="X", action="canceled")
        # Cancel with context
        tracker.record(
            task_id="b",
            task_title="Review report",
            task_notes="Important quarterly review",
            action="canceled",
        )

        summary = tracker.get_summary(days=7)
        # "X" is vague-capture, "Review report" is follow-up
        assert summary["no_context_cancel_rate"] == 0.5
