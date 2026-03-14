"""Tests for input validation."""

import pytest
from fastmcp.exceptions import ToolError

from things_mcp.input_validation import validate_tag_names, validate_show_id


class TestValidateTagNames:
    def test_valid_simple(self):
        validate_tag_names(["work", "home", "office"])

    def test_valid_with_at_prefix(self):
        validate_tag_names(["@computer", "@phone", "@errands"])

    def test_valid_with_hyphens(self):
        validate_tag_names(["high-energy", "waiting-for"])

    def test_valid_with_spaces(self):
        validate_tag_names(["Work Tasks", "Side Projects"])

    def test_valid_with_underscores(self):
        validate_tag_names(["my_tag", "test_123"])

    def test_valid_none(self):
        validate_tag_names(None)

    def test_valid_empty_list(self):
        validate_tag_names([])

    def test_rejects_quotes(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            validate_tag_names(['test"injection'])

    def test_rejects_semicolons(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            validate_tag_names(["test;drop"])

    def test_rejects_applescript_injection(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            validate_tag_names(['"; do shell script "rm -rf /"'])

    def test_rejects_angle_brackets(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            validate_tag_names(["<script>alert(1)</script>"])

    def test_rejects_ampersand(self):
        with pytest.raises(ToolError, match="Invalid tag name"):
            validate_tag_names(["foo&bar"])


class TestValidateShowId:
    def test_valid_list_names(self):
        for name in ["inbox", "today", "upcoming", "anytime", "someday", "logbook"]:
            validate_show_id(name)

    def test_valid_uuid(self):
        validate_show_id("HENteMSvX4LPsQcS3YP1U")

    def test_valid_uuid_with_hyphens(self):
        validate_show_id("abc-def-123")

    def test_rejects_html(self):
        with pytest.raises(ToolError, match="Invalid id"):
            validate_show_id("<script>alert(1)</script>")

    def test_rejects_empty(self):
        with pytest.raises(ToolError, match="Invalid id"):
            validate_show_id("")

    def test_rejects_spaces(self):
        with pytest.raises(ToolError, match="Invalid id"):
            validate_show_id("some thing")
