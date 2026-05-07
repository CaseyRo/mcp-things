"""Tests for the make_result / write_result / bulk_result helpers."""

import pytest

from things_mcp.models import BulkItemError, BulkResult, ToolEnvelope, WriteResult
from things_mcp.tool_results import bulk_result, make_result, write_result

pytestmark = [pytest.mark.unit]


class TestMakeResult:
    def test_structured_content_validates_against_envelope(self):
        result = make_result(data=None, summary="ok")
        env = ToolEnvelope.model_validate(result.structured_content)
        assert env.summary == "ok"
        assert env.data is None
        assert env.meta == {}

    def test_text_defaults_to_summary(self):
        result = make_result(data=None, summary="hello")
        assert len(result.content) == 1
        assert result.content[0].text == "hello"
        assert result.content[0].type == "text"

    def test_explicit_text_overrides_summary(self):
        result = make_result(data=None, summary="machine", text="human readable")
        assert result.content[0].text == "human readable"
        env = ToolEnvelope.model_validate(result.structured_content)
        assert env.summary == "machine"

    def test_meta_round_trips(self):
        result = make_result(data=None, summary="ok", meta={"warning": "stale cache"})
        env = ToolEnvelope.model_validate(result.structured_content)
        assert env.meta == {"warning": "stale cache"}


class TestWriteResult:
    def test_write_result_default_acknowledged(self):
        result = write_result(summary="captured", thing_id="ABC")
        wr = WriteResult.model_validate(result.structured_content["data"])
        assert wr.acknowledged is True
        assert wr.thing_id == "ABC"

    def test_write_result_can_signal_unacknowledged(self):
        result = write_result(summary="degraded", acknowledged=False)
        wr = WriteResult.model_validate(result.structured_content["data"])
        assert wr.acknowledged is False
        assert wr.thing_id is None


class TestBulkResult:
    def test_bulk_result_counts_match_ids(self):
        result = bulk_result(
            requested=3,
            succeeded_ids=["A", "B"],
            failed_ids=["C"],
            errors=[BulkItemError(task_id="C", action="complete", reason="oops")],
            summary="2/3 succeeded",
        )
        bulk = BulkResult.model_validate(result.structured_content["data"])
        assert bulk.requested == 3
        assert bulk.succeeded == 2
        assert bulk.failed == 1
        assert bulk.succeeded_ids == ["A", "B"]
        assert bulk.failed_ids == ["C"]
        assert len(bulk.errors) == 1

    def test_bulk_result_counts_batch_level_failures(self):
        """A null-task_id error increments `failed` even without a failed_id."""
        result = bulk_result(
            requested=5,
            succeeded_ids=[],
            failed_ids=[],
            errors=[
                BulkItemError(
                    task_id=None, action="complete", reason="AppleScript failed"
                )
            ],
            summary="batch failed",
        )
        bulk = BulkResult.model_validate(result.structured_content["data"])
        assert bulk.failed == 1
        assert bulk.succeeded == 0

    def test_bulk_result_includes_by_action(self):
        result = bulk_result(
            requested=3,
            succeeded_ids=["A", "B", "C"],
            failed_ids=[],
            errors=[],
            summary="3/3",
            by_action={"complete": 2, "defer": 1},
        )
        bulk = BulkResult.model_validate(result.structured_content["data"])
        assert bulk.by_action == {"complete": 2, "defer": 1}
