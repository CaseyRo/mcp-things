"""Unit tests for schema transformation functions.

Tests the client compatibility transformations for n8n and ChatGPT.
"""

from things_mcp.server_core import (
    _flatten_anyof_for_n8n,
    _add_additional_properties_false,
    _make_all_fields_required,
)


class TestFlattenAnyOf:
    """Tests for _flatten_anyof_for_n8n function."""

    def test_flatten_simple_optional(self):
        """Test flattening a simple Optional[str] schema."""
        schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        result = _flatten_anyof_for_n8n(schema)
        assert result == {"type": ["string", "null"]}

    def test_flatten_nested_in_properties(self):
        """Test flattening anyOf nested in properties."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "notes": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
        }
        result = _flatten_anyof_for_n8n(schema)
        assert result["properties"]["title"] == {"type": "string"}
        assert result["properties"]["notes"] == {"type": ["string", "null"]}

    def test_preserve_non_anyof_fields(self):
        """Test that non-anyOf fields are preserved."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "A name"}},
            "required": ["name"],
        }
        result = _flatten_anyof_for_n8n(schema)
        assert result == schema


class TestAddAdditionalPropertiesFalse:
    """Tests for _add_additional_properties_false function."""

    def test_add_to_simple_object(self):
        """Test adding additionalProperties to a simple object."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = _add_additional_properties_false(schema)
        assert result["additionalProperties"] is False

    def test_preserve_existing_additional_properties(self):
        """Test that existing additionalProperties is preserved."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": True,
        }
        result = _add_additional_properties_false(schema)
        assert result["additionalProperties"] is True

    def test_add_to_nested_objects(self):
        """Test adding additionalProperties to nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                }
            },
        }
        result = _add_additional_properties_false(schema)
        assert result["additionalProperties"] is False
        assert result["properties"]["user"]["additionalProperties"] is False

    def test_add_to_array_items(self):
        """Test adding additionalProperties to array item objects."""
        schema = {
            "type": "array",
            "items": {"type": "object", "properties": {"id": {"type": "integer"}}},
        }
        result = _add_additional_properties_false(schema)
        assert result["items"]["additionalProperties"] is False


class TestMakeAllFieldsRequired:
    """Tests for _make_all_fields_required function."""

    def test_make_optional_field_required_and_nullable(self):
        """Test that optional fields are made required with nullable type."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        }
        result = _make_all_fields_required(schema)
        assert set(result["required"]) == {"title", "notes"}
        assert result["properties"]["title"]["type"] == "string"
        assert result["properties"]["notes"]["type"] == ["string", "null"]

    def test_already_nullable_stays_nullable(self):
        """Test that already nullable fields stay nullable."""
        schema = {
            "type": "object",
            "properties": {
                "notes": {"type": ["string", "null"]},
            },
            "required": [],
        }
        result = _make_all_fields_required(schema)
        assert result["required"] == ["notes"]
        # Should not add duplicate null
        assert result["properties"]["notes"]["type"] == ["string", "null"]

    def test_required_field_stays_non_nullable(self):
        """Test that required fields stay non-nullable."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
            },
            "required": ["title"],
        }
        result = _make_all_fields_required(schema)
        assert result["properties"]["title"]["type"] == "string"

    def test_nested_objects_processed(self):
        """Test that nested objects are also processed."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                    "required": ["name"],
                }
            },
            "required": ["user"],
        }
        result = _make_all_fields_required(schema)
        user_props = result["properties"]["user"]
        assert set(user_props["required"]) == {"name", "email"}
        assert user_props["properties"]["email"]["type"] == ["string", "null"]


class TestFullTransformationPipeline:
    """Test the full transformation pipeline as used in production."""

    def test_complete_transformation(self):
        """Test a complete transformation matching production use."""
        # Input schema similar to what Pydantic generates for a tool
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "notes": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Optional notes",
                },
                "tags": {
                    "anyOf": [
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "null"},
                    ],
                    "description": "Optional tags",
                },
            },
            "required": ["title"],
        }

        # Apply transformations in order
        result = _flatten_anyof_for_n8n(schema)
        result = _add_additional_properties_false(result)
        result = _make_all_fields_required(result)

        # Verify the output matches ChatGPT's requirements
        assert result["additionalProperties"] is False
        assert set(result["required"]) == {"title", "notes", "tags"}

        # Title should remain non-nullable (was required)
        assert result["properties"]["title"]["type"] == "string"

        # Notes should be nullable (was optional)
        assert result["properties"]["notes"]["type"] == ["string", "null"]

        # Tags should be nullable array (was optional)
        assert result["properties"]["tags"]["type"] == ["array", "null"]
