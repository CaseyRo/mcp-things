"""Tests for server_core middleware behavior.

Focus (CDI-1167): the clear-sentinel used to clear a deadline / start date must
survive ``ClientCompatibilityMiddleware.on_call_tool`` so the clear is not
silently swallowed before reaching the tool handler.
"""

from types import SimpleNamespace

import pytest

from things_mcp.server_core import ClientCompatibilityMiddleware


pytestmark = [pytest.mark.unit]


class _FakeMessage:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


async def _call(middleware, name, arguments):
    """Drive on_call_tool, capturing the arguments seen by the inner handler."""
    captured = {}
    context = SimpleNamespace(message=_FakeMessage(name, arguments))

    async def call_next(ctx):
        # Snapshot what survived the middleware sanitization.
        captured["args"] = dict(ctx.message.arguments)
        return "ok"

    result = await middleware.on_call_tool(context, call_next)
    return result, captured


@pytest.mark.asyncio
async def test_non_empty_clear_sentinel_survives_middleware():
    """A non-empty sentinel (the documented clear value) reaches the handler.

    The middleware strips only explicit nulls (which mean "not provided"), so a
    non-empty sentinel such as "none" must pass through untouched.
    """
    mw = ClientCompatibilityMiddleware()
    result, captured = await _call(
        mw, "modify-task", {"task_id": "abc", "deadline": "none", "when": "clear"}
    )
    assert result == "ok"
    assert captured["args"]["deadline"] == "none"
    assert captured["args"]["when"] == "clear"


@pytest.mark.asyncio
async def test_null_optional_is_stripped():
    """Explicit nulls (n8n behavior) are stripped — they mean 'not provided'."""
    mw = ClientCompatibilityMiddleware()
    _, captured = await _call(mw, "modify-task", {"task_id": "abc", "deadline": None})
    assert "deadline" not in captured["args"]
    assert captured["args"]["task_id"] == "abc"


@pytest.mark.asyncio
async def test_n8n_extra_params_stripped_but_sentinel_kept():
    mw = ClientCompatibilityMiddleware()
    _, captured = await _call(
        mw,
        "modify-task",
        {"task_id": "abc", "deadline": "none", "toolCallId": "x", "sessionId": "y"},
    )
    assert "toolCallId" not in captured["args"]
    assert "sessionId" not in captured["args"]
    # The clear-sentinel is preserved alongside the n8n-param strip.
    assert captured["args"]["deadline"] == "none"
