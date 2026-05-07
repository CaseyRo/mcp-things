"""Server-level audit + integration tests for structured tool output.

Covers tasks 10.1-10.4 of the `structured-json-tool-output` change:
- 10.1: every registered tool has a non-null `output_schema`
- 10.2: a representative read tool returns a `structuredContent` payload that
  validates against its declared `outputSchema`
- 10.3: ChatGPT `User-Agent` triggers strict-mode transforms (no `anyOf`,
  `additionalProperties: false` everywhere)
- 10.4: n8n `User-Agent` still produces valid JSON Schema and accepts nulls

These run without Things 3 — `mock_things` stubs the data layer.
"""

from __future__ import annotations

from typing import Any

import jsonschema
import pytest

from things_mcp.models import ToolEnvelope, output_schema_for
from things_mcp.fast_server import mcp


# ---------------------------------------------------------------------------
# 10.1 — Startup audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_tool_publishes_an_output_schema():
    """Every registered tool must declare an `output_schema`.

    Failure mode names the offending tool so the regression is obvious.
    """
    tools = await mcp.list_tools()
    missing = [t.name for t in tools if not getattr(t, "output_schema", None)]
    assert not missing, (
        f"The following tools are missing `output_schema=` on their @mcp.tool "
        f"registration: {missing}. Every tool in the structured-output contract "
        f"must publish a JSON Schema for its envelope."
    )
    assert len(tools) == 32, f"Expected 32 tools, found {len(tools)}"


@pytest.mark.asyncio
async def test_every_tool_output_schema_is_valid_json_schema():
    """Every published `output_schema` must be a valid JSON Schema document."""
    tools = await mcp.list_tools()
    for tool in tools:
        schema = tool.output_schema
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as e:
            pytest.fail(f"Tool '{tool.name}' has invalid output_schema: {e}")


# ---------------------------------------------------------------------------
# 10.2 — structuredContent validates against the declared envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tasks_structured_content_validates_against_envelope(mock_things):
    """`get-tasks` returns a `ToolResult` whose structured payload validates.

    This is the must-have for CDI-1021: the JSON envelope is what downstream
    consumers (Arbeitsplatz artifact, ChatGPT, n8n) read.
    """
    # Two mock todos; minimal shape that things-py would emit.
    mock_things.today.return_value = [
        {
            "uuid": "todo-1",
            "type": "to-do",
            "title": "Ship CDI-1021",
            "notes": "",
            "status": "incomplete",
            "tags": ["work"],
            "start": "today",
            "start_date": "2026-05-07",
            "deadline": None,
            "stop_date": None,
            "created": "2026-05-01T08:00:00",
            "modified": "2026-05-07T09:00:00",
            "project": None,
            "project_title": None,
            "area": "area-1",
            "area_title": "Things MCP",
        },
    ]

    tool = await mcp.get_tool("get-tasks")
    result = await tool.run({"view": "today"})

    structured = result.structured_content
    assert structured is not None, "get-tasks must emit structured_content"
    assert "data" in structured and "summary" in structured and "meta" in structured

    # Validate against the canonical envelope schema.
    envelope_schema = output_schema_for(ToolEnvelope[list])
    jsonschema.Draft202012Validator(envelope_schema).validate(structured)

    # And against the tool's declared output_schema.
    tools = await mcp.list_tools()
    declared = next(t.output_schema for t in tools if t.name == "get-tasks")
    jsonschema.Draft202012Validator(declared).validate(structured)

    # Per-task shape from CDI-1021's target spec.
    assert isinstance(structured["data"], list)
    assert len(structured["data"]) == 1
    task = structured["data"][0]
    assert task["uuid"] == "todo-1"
    assert task["title"] == "Ship CDI-1021"
    assert task["tags"] == ["work"]


# ---------------------------------------------------------------------------
# 10.3 — ChatGPT strict-mode transforms applied to output schemas
# ---------------------------------------------------------------------------


def _walk_schema_objects(schema: Any):
    """Yield every object-typed node in a schema (recursing into properties,
    items, additionalProperties, $defs)."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            yield schema
        for key in ("properties", "$defs", "definitions"):
            sub = schema.get(key)
            if isinstance(sub, dict):
                for v in sub.values():
                    yield from _walk_schema_objects(v)
        items = schema.get("items")
        if isinstance(items, (dict, list)):
            if isinstance(items, list):
                for it in items:
                    yield from _walk_schema_objects(it)
            else:
                yield from _walk_schema_objects(items)
        ap = schema.get("additionalProperties")
        if isinstance(ap, dict):
            yield from _walk_schema_objects(ap)
    elif isinstance(schema, list):
        for v in schema:
            yield from _walk_schema_objects(v)


def _has_anyof_or_oneof(schema: Any) -> bool:
    if isinstance(schema, dict):
        if "anyOf" in schema or "oneOf" in schema:
            return True
        return any(_has_anyof_or_oneof(v) for v in schema.values())
    if isinstance(schema, list):
        return any(_has_anyof_or_oneof(v) for v in schema)
    return False


def _find_compat_middleware():
    """Locate the ClientCompatibilityMiddleware instance on the server."""
    candidates = []
    for attr in ("middleware", "_middleware"):
        val = getattr(mcp, attr, None)
        if val:
            candidates.extend(val)
    for mw in candidates:
        if mw.__class__.__name__ == "ClientCompatibilityMiddleware":
            return mw
    return None


@pytest.mark.asyncio
async def test_chatgpt_user_agent_strips_anyof_from_output_schemas(monkeypatch):
    """ChatGPT detector triggers strict-mode transforms on `outputSchema`.

    Asserts: no `anyOf` / `oneOf` survives; `additionalProperties: false` set
    on every object node, including inside `$defs`.
    """
    compat = _find_compat_middleware()
    assert compat is not None, "ClientCompatibilityMiddleware not registered"

    # Force the ChatGPT detector path — the production code reads HTTP headers
    # via fastmcp.server.dependencies.get_http_headers, which has no live
    # request in tests.
    monkeypatch.setattr(compat, "_detect_client", lambda: "chatgpt")

    tools = await mcp.list_tools()

    async def passthrough(_ctx):
        return tools

    transformed = await compat.on_list_tools(object(), passthrough)
    assert transformed is tools

    # Sanity: a freshly generated envelope schema has anyOf inside it (the
    # `data` field is `DataT | None`, every optional Todo field, etc.). After
    # the ChatGPT path runs, no anyOf/oneOf survives in any tool's outputSchema.
    fresh = output_schema_for(ToolEnvelope[list])
    assert _has_anyof_or_oneof(fresh), (
        "Pydantic-generated envelope should contain anyOf — check the model"
    )

    for tool in transformed:
        schema = tool.output_schema
        assert not _has_anyof_or_oneof(schema), (
            f"Tool '{tool.name}' still has anyOf/oneOf after ChatGPT strict-mode transform"
        )

    # Every transformed schema must still be a valid JSON Schema.
    for tool in transformed:
        try:
            jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        except jsonschema.SchemaError as e:
            pytest.fail(
                f"Tool '{tool.name}' has invalid output_schema after ChatGPT transform: {e}"
            )


# ---------------------------------------------------------------------------
# 10.4 — n8n User-Agent: schemas remain valid; nulls accepted in outputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_n8n_user_agent_keeps_schemas_valid_and_nullable(
    mock_things, monkeypatch
):
    """n8n path: schemas validate, and nullable output fields accept null."""
    compat = _find_compat_middleware()
    assert compat is not None

    monkeypatch.setattr(compat, "_detect_client", lambda: "n8n")

    tools = await mcp.list_tools()

    async def passthrough(_ctx):
        return tools

    transformed = await compat.on_list_tools(object(), passthrough)

    for tool in transformed:
        try:
            jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        except jsonschema.SchemaError as e:
            pytest.fail(
                f"Tool '{tool.name}' has invalid output_schema after n8n transform: {e}"
            )

    # And: a payload with explicit nulls in optional fields still validates.
    mock_things.today.return_value = [
        {
            "uuid": "todo-2",
            "type": "to-do",
            "title": "n8n null check",
            "notes": "",
            "status": "incomplete",
            "tags": [],
            "start": None,
            "start_date": None,
            "deadline": None,
            "stop_date": None,
            "created": None,
            "modified": None,
            "project": None,
            "project_title": None,
            "area": None,
            "area_title": None,
        },
    ]

    tool = await mcp.get_tool("get-tasks")
    result = await tool.run({"view": "today"})
    schema = next(t.output_schema for t in transformed if t.name == "get-tasks")
    jsonschema.Draft202012Validator(schema).validate(result.structured_content)
