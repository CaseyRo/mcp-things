"""Tests for log redaction patterns."""

from things_mcp.logging_config import _redact_message_text, REDACTION_TOKEN


class TestRedactMessageText:
    """Test inline message redaction patterns."""

    def test_title_redacted(self):
        result = _redact_message_text("title=Buy milk&completed=true")
        assert "Buy" not in result
        assert REDACTION_TOKEN in result

    def test_notes_redacted(self):
        result = _redact_message_text("notes=secret stuff&when=today")
        assert "secret" not in result
        assert REDACTION_TOKEN in result

    def test_auth_token_redacted(self):
        result = _redact_message_text("auth-token=MYSECRET&id=123")
        assert "MYSECRET" not in result
        assert REDACTION_TOKEN in result

    def test_title_stops_at_ampersand(self):
        """Title pattern must not consume auth-token after &."""
        result = _redact_message_text("title=Hello&auth-token=SECRET123")
        # Both should be independently redacted
        assert "Hello" not in result
        assert "SECRET123" not in result

    def test_auth_token_stops_at_ampersand(self):
        result = _redact_message_text("auth-token=SECRET&completed=true")
        assert "SECRET" not in result
        assert "completed=true" in result

    def test_no_match_passes_through(self):
        msg = "Just a normal log message"
        assert _redact_message_text(msg) == msg

    def test_params_redacted(self):
        result = _redact_message_text("params=sensitive_data&extra=ok")
        assert "sensitive_data" not in result

    def test_tags_redacted(self):
        result = _redact_message_text("tags=personal-tag&id=abc")
        assert "personal-tag" not in result

    def test_case_insensitive(self):
        result = _redact_message_text("Title=Private Info&done=true")
        assert "Private" not in result
