"""Tests for the structured-output Pydantic models and envelope contract."""

import pytest
from jsonschema import Draft202012Validator

from things_mcp.models import (
    Area,
    BulkItemError,
    BulkResult,
    CacheStats,
    ChecklistItem,
    FocusResult,
    Project,
    ReviewReport,
    ShowInAppResult,
    Tag,
    Todo,
    ToolEnvelope,
    TriageActionStats,
    TriageInsights,
    WriteResult,
    output_schema_for,
)
from things_mcp.server_core import (
    _add_additional_properties_false,
    _flatten_anyof_for_n8n,
    _make_all_fields_required,
)

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestModelRoundTrips:
    """Each model must round-trip through model_dump(mode='json') losslessly."""

    def test_todo_round_trip(self):
        todo = Todo(
            uuid="ABC-1",
            title="Buy milk",
            tags=["@errands"],
            checklist=[ChecklistItem(title="2L", status="open")],
            deadline="2026-05-01",
            project="P1",
            project_title="Errands",
        )
        payload = todo.model_dump(mode="json")
        restored = Todo.model_validate(payload)
        assert restored == todo

    def test_project_round_trip(self):
        project = Project(uuid="P1", title="Q2 Plan", tags=["work"])
        assert Project.model_validate(project.model_dump(mode="json")) == project

    def test_area_round_trip(self):
        area = Area(uuid="A1", title="Personal")
        assert Area.model_validate(area.model_dump(mode="json")) == area

    def test_tag_round_trip(self):
        tag = Tag(uuid="T1", title="@computer", shortcut="c")
        assert Tag.model_validate(tag.model_dump(mode="json")) == tag

    def test_envelope_with_list_data(self):
        env = ToolEnvelope[list[Todo]](
            data=[Todo(uuid="X", title="X")], summary="1 item"
        )
        restored = ToolEnvelope[list[Todo]].model_validate(env.model_dump(mode="json"))
        assert restored.data[0].uuid == "X"
        assert restored.summary == "1 item"

    def test_envelope_with_null_data(self):
        env = ToolEnvelope[WriteResult](
            data=None, summary="ack", meta={"warning": "stale"}
        )
        restored = ToolEnvelope[WriteResult].model_validate(env.model_dump(mode="json"))
        assert restored.data is None
        assert restored.meta == {"warning": "stale"}

    def test_write_result_round_trip(self):
        wr = WriteResult(acknowledged=True, thing_id="ABC", summary="captured")
        assert WriteResult.model_validate(wr.model_dump(mode="json")) == wr

    def test_bulk_result_round_trip(self):
        bulk = BulkResult(
            requested=3,
            succeeded=2,
            failed=1,
            succeeded_ids=["A", "B"],
            failed_ids=["C"],
            errors=[BulkItemError(task_id="C", action="complete", reason="not found")],
            by_action={"complete": 3},
        )
        assert BulkResult.model_validate(bulk.model_dump(mode="json")) == bulk

    def test_focus_result_round_trip(self):
        fr = FocusResult(
            task=Todo(uuid="X", title="X"),
            selection_reason="overdue",
            selection_detail="deadline was 2026-04-20",
        )
        assert FocusResult.model_validate(fr.model_dump(mode="json")) == fr

    def test_review_report_round_trip(self):
        rr = ReviewReport(period="daily", inbox_count=3, upcoming_count=5)
        assert ReviewReport.model_validate(rr.model_dump(mode="json")) == rr

    def test_triage_insights_round_trip(self):
        ti = TriageInsights(
            period_days=7,
            total=10,
            avg_per_day=1.4,
            actions=[TriageActionStats(action="completed", count=5, percent=50)],
        )
        assert TriageInsights.model_validate(ti.model_dump(mode="json")) == ti

    def test_cache_stats_round_trip(self):
        cs = CacheStats(entries=10, hits=8, misses=2, hit_rate="80%", total_requests=10)
        assert CacheStats.model_validate(cs.model_dump(mode="json")) == cs

    def test_show_in_app_result_round_trip(self):
        sa = ShowInAppResult(opened="inbox")
        assert ShowInAppResult.model_validate(sa.model_dump(mode="json")) == sa


# ---------------------------------------------------------------------------
# JSON Schema generation
# ---------------------------------------------------------------------------


class TestOutputSchema:
    """`output_schema_for` produces valid, ChatGPT-strict-safe JSON schemas."""

    def test_todo_envelope_schema_is_valid(self):
        schema = output_schema_for(ToolEnvelope[Todo])
        Draft202012Validator.check_schema(schema)

    def test_envelope_advertises_three_fields(self):
        schema = output_schema_for(ToolEnvelope[Todo])
        # The actual `properties` may be flattened differently by Pydantic, but
        # must include data, summary, meta keys at the top level.
        props = schema.get("properties") or {}
        assert "data" in props
        assert "summary" in props
        assert "meta" in props

    def test_strict_transform_removes_anyof_in_top_level(self):
        """ChatGPT strict mode requires no anyOf/oneOf to remain — top-level."""
        schema = output_schema_for(ToolEnvelope[Todo])
        transformed = _flatten_anyof_for_n8n(schema)
        transformed = _add_additional_properties_false(transformed)
        transformed = _make_all_fields_required(transformed)
        assert _has_no_anyof(transformed), (
            "anyOf/oneOf survived strict transform: " + repr(transformed)
        )

    def test_strict_transform_recurses_into_defs(self):
        """Pydantic puts nested models in $defs — flattener must recurse there."""
        schema = output_schema_for(ToolEnvelope[Project])
        # Project nests Todo + ChecklistItem in $defs and Todo has Optional fields.
        assert "$defs" in schema
        transformed = _flatten_anyof_for_n8n(schema)
        transformed = _add_additional_properties_false(transformed)
        transformed = _make_all_fields_required(transformed)
        assert _has_no_anyof(transformed), "anyOf survived in $defs: " + repr(
            transformed.get("$defs")
        )

    def test_strict_transform_adds_additional_properties_false_in_defs(self):
        schema = output_schema_for(ToolEnvelope[Project])
        transformed = _add_additional_properties_false(schema)
        for name, def_schema in transformed.get("$defs", {}).items():
            if def_schema.get("type") == "object" or "properties" in def_schema:
                assert def_schema.get("additionalProperties") is False, (
                    f"$defs.{name} missing additionalProperties: false"
                )

    def test_non_chatgpt_path_leaves_anyof_intact(self):
        """When ChatGPT transforms are skipped, raw Pydantic schema may keep anyOf."""
        # The flattener still runs for n8n (it converts anyOf -> type arrays),
        # so after _flatten_anyof_for_n8n alone we expect no anyOf — that's
        # intentional. This test just records the shape so future changes don't
        # accidentally drop the flattener for non-ChatGPT clients.
        schema = output_schema_for(ToolEnvelope[Todo])
        transformed = _flatten_anyof_for_n8n(schema)
        assert _has_no_anyof(transformed)


def _has_no_anyof(obj) -> bool:
    """Return True if the object (and every nested dict/list) has no anyOf or oneOf."""
    if isinstance(obj, dict):
        if "anyOf" in obj or "oneOf" in obj:
            return False
        return all(_has_no_anyof(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_has_no_anyof(item) for item in obj)
    return True


# ---------------------------------------------------------------------------
# Defaults & invariants
# ---------------------------------------------------------------------------


class TestModelInvariants:
    def test_todo_defaults_tags_and_checklist_to_empty_list(self):
        todo = Todo(uuid="X", title="X")
        assert todo.tags == []
        assert todo.checklist == []

    def test_envelope_meta_defaults_to_empty_dict(self):
        env = ToolEnvelope(data=None, summary="ok")
        assert env.meta == {}

    def test_envelope_summary_is_optional_and_defaults_to_empty(self):
        """Hardened envelope: omitting `summary` must not raise (footgun fix).

        Internal paths that forget to set a summary should get an empty
        headline instead of a runtime ValidationError.
        """
        env = ToolEnvelope(data=None)
        assert env.summary == ""
        # Same via model_validate (the structured-output path).
        validated = ToolEnvelope.model_validate({"data": None})
        assert validated.summary == ""

    def test_envelope_ignores_unexpected_extra_key(self):
        """Hardened envelope: an unexpected extra key must be dropped, not raise.

        ClientCompatibilityMiddleware already strips extras on the wire; this
        guarantees the model itself degrades gracefully if one slips through.
        """
        # Construction with an unexpected kwarg must not raise.
        env = ToolEnvelope(data=None, summary="ok", unexpected="boom")
        assert env.summary == "ok"
        assert not hasattr(env, "unexpected")
        # And via model_validate (the round-trip path).
        validated = ToolEnvelope.model_validate(
            {"data": None, "summary": "ok", "extra": 1}
        )
        assert validated.summary == "ok"
        # The extra key is ignored, so the serialized shape clients see is
        # unchanged (data/summary/meta only).
        assert set(validated.model_dump().keys()) == {"data", "summary", "meta"}

    def test_envelope_no_args_does_not_raise(self):
        """Belt-and-suspenders: a fully bare envelope is constructible."""
        env = ToolEnvelope()
        assert env.data is None
        assert env.summary == ""
        assert env.meta == {}

    def test_todo_status_enum_enforced(self):
        with pytest.raises(Exception):
            Todo(uuid="X", title="X", status="bogus")
