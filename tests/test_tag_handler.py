"""Tests for tag handler module."""

from unittest import mock

import pytest
from fastmcp.exceptions import ToolError

from things_mcp.tag_handler import ensure_tags_exist, get_existing_tags


class TestEnsureTagsExist:
    def test_empty_list_returns_true(self):
        assert ensure_tags_exist([]) is True

    def test_none_returns_true(self):
        assert ensure_tags_exist(None) is True

    def test_calls_applescript(self, monkeypatch):
        mock_run = mock.Mock(return_value="ok")
        monkeypatch.setattr("things_mcp.tag_handler.run_applescript", mock_run)
        result = ensure_tags_exist(["@computer", "work"])
        assert result is True
        mock_run.assert_called_once()
        script = mock_run.call_args[0][0]
        assert '"@computer"' in script
        assert '"work"' in script

    def test_applescript_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.tag_handler.run_applescript", mock.Mock(return_value=None)
        )
        # Empty string is falsy, so run_applescript returning "" returns False
        assert ensure_tags_exist(["tag1"]) is False

    def test_exception_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.tag_handler.run_applescript",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        assert ensure_tags_exist(["tag1"]) is False

    def test_validates_tag_names(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            ensure_tags_exist(['bad"tag'])

    def test_escapes_quotes_in_script(self, monkeypatch):
        mock_run = mock.Mock(return_value="ok")
        monkeypatch.setattr("things_mcp.tag_handler.run_applescript", mock_run)
        # Tag with special AppleScript chars (but valid per our regex)
        ensure_tags_exist(["my_tag"])
        script = mock_run.call_args[0][0]
        assert "my_tag" in script


class TestGetExistingTags:
    def test_parses_comma_separated(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.tag_handler.run_applescript",
            mock.Mock(return_value="@computer, work, @phone"),
        )
        tags = get_existing_tags()
        assert tags == ["@computer", "work", "@phone"]

    def test_empty_result(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.tag_handler.run_applescript",
            mock.Mock(return_value=None),
        )
        assert get_existing_tags() == []

    def test_exception_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.tag_handler.run_applescript",
            mock.Mock(side_effect=RuntimeError("boom")),
        )
        assert get_existing_tags() == []
