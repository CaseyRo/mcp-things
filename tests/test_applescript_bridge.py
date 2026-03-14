"""Tests for AppleScript bridge module."""

from unittest import mock


from things_mcp.applescript_bridge import (
    _script_metadata,
    _wrap_script_for_background,
    escape_applescript_string,
    run_applescript,
)


class TestEscapeApplescriptString:
    def test_no_special_chars(self):
        assert escape_applescript_string("hello world") == "hello world"

    def test_double_quotes(self):
        assert escape_applescript_string('say "hi"') == 'say ""hi""'

    def test_empty_string(self):
        assert escape_applescript_string("") == ""

    def test_multiple_quotes(self):
        assert escape_applescript_string('"a" "b"') == '""a"" ""b""'


class TestScriptMetadata:
    def test_single_line(self):
        meta = _script_metadata("test", "return 1")
        assert meta["command"] == "test"
        assert meta["line_count"] == 1
        assert meta["char_count"] == 8

    def test_multi_line(self):
        script = "line1\nline2\nline3"
        meta = _script_metadata("run", script)
        assert meta["line_count"] == 3


class TestWrapScriptForBackground:
    def test_returns_script_unchanged(self):
        script = 'tell application "Things3"\n  return name\nend tell'
        assert _wrap_script_for_background(script) == script

    def test_non_things_script(self):
        script = 'tell application "Finder"\n  return name\nend tell'
        assert _wrap_script_for_background(script) == script

    def test_disabled_via_settings(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.applescript_bridge.get_settings",
            lambda: mock.Mock(things_mcp_disable_background_osascript=True),
        )
        script = 'tell application "Things3"\n  return name\nend tell'
        assert _wrap_script_for_background(script) == script


class TestRunApplescript:
    def test_single_line_uses_dash_e(self, monkeypatch):
        mock_run = mock.Mock(
            return_value=mock.Mock(returncode=0, stdout="result\n", stderr="")
        )
        monkeypatch.setattr("things_mcp.applescript_bridge.subprocess.run", mock_run)
        result = run_applescript("return 1")
        assert result == "result"
        args = mock_run.call_args[0][0]
        assert args == ["osascript", "-e", "return 1"]

    def test_multi_line_uses_stdin(self, monkeypatch):
        mock_run = mock.Mock(
            return_value=mock.Mock(returncode=0, stdout="ok\n", stderr="")
        )
        monkeypatch.setattr("things_mcp.applescript_bridge.subprocess.run", mock_run)
        result = run_applescript("line1\nline2")
        assert result == "ok"
        args = mock_run.call_args[0][0]
        assert args == ["osascript"]
        assert mock_run.call_args[1]["input"] == "line1\nline2"

    def test_error_returns_false(self, monkeypatch):
        mock_run = mock.Mock(
            return_value=mock.Mock(returncode=1, stdout="", stderr="error msg")
        )
        monkeypatch.setattr("things_mcp.applescript_bridge.subprocess.run", mock_run)
        assert run_applescript("bad script") is False

    def test_exception_returns_false(self, monkeypatch):
        monkeypatch.setattr(
            "things_mcp.applescript_bridge.subprocess.run",
            mock.Mock(side_effect=OSError("not found")),
        )
        assert run_applescript("anything") is False
