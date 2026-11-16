"""Canonical MCP usage-telemetry middleware. Vendor this file into each fleet server.

One JSON line per tool call on stderr (stdout would corrupt stdio transports):
    {"mcp_usage": 1, "ts": "...", "server": "siyuan", "tool": "get_block",
     "duration_ms": 42, "outcome": "ok", "protocol": "2026-07-28"}
A failed call adds why: "error_type" (exception class) and "error" (first line,
max 200 chars, secrets redacted; validation errors give field and type only).

No arguments, no results. A failure inside telemetry never touches the call.
Works on fastmcp 4.x (`on_call_tool` hook).

Register:  mcp.add_middleware(UsageMiddleware("siyuan"))
Non-tool routes (e.g. `@mcp.custom_route` REST hooks) bypass the middleware;
record those with  emit("siyuan", "hook/query", duration_ms, "ok")
Spec:      openspec/changes/upgrade-fleet-fastmcp-4/specs/mcp-usage-telemetry/spec.md
"""
from __future__ import annotations

import json
import re
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone

from fastmcp.server.middleware import Middleware
from pydantic import ValidationError

# key=value / bearer secrets, URL credentials, JWTs and long opaque strings (keys, tokens)
_SECRET = re.compile(
    r"(?i)((?:token|api[_-]?key|key|secret|passw(?:or)?d|pwd|authorization|cookie)[\"']?\s*[=:]\s*[\"']?"
    r"(?:(?:bearer|basic)\s+)?|(?:bearer|basic)\s+)[^\s\"',;&]+"
)
_OPAQUE = re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)|\beyJ[\w-]+\.[\w-]+\.[\w-]*|\b[\w-]{32,}")


def _short(msg):
    msg = (str(msg).strip().splitlines() or [""])[0]
    return _OPAQUE.sub("[redacted]", _SECRET.sub(r"\1[redacted]", msg))[:200]


def describe(exc):
    """(error_type, short redacted message) for a failed call. Never echoes arguments."""
    if not isinstance(exc, BaseException):  # a returned is_error result
        return "ToolResult", _short(getattr((exc.content or [None])[0], "text", ""))
    cause = exc.__cause__ or exc  # fastmcp wraps tool exceptions in ToolError("Error calling tool ...")
    if isinstance(cause, ValidationError):  # field and type only: its input values are the arguments
        msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in cause.errors())
    else:
        msg = cause if str(exc).startswith("Error calling tool") else exc
    return type(cause).__name__, _short(msg)


def emit(server, tool, duration_ms, outcome, protocol=None, error_type=None, error=None):
    """Write one usage line to stderr. Never raises."""
    with suppress(Exception):  # telemetry never affects the call
        rec = {
            "mcp_usage": 1,
            # timezone.utc keeps 3.10 support
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),  # noqa: UP017
            "server": server,
            "tool": tool,
            "duration_ms": duration_ms,
            "outcome": outcome,
            # Negotiated MCP era (e.g. 2026-07-28 vs 2025-06-18).
            "protocol": protocol,
        }
        if outcome == "error" and error_type:
            rec.update(error_type=error_type, error=error)
        sys.stderr.write(json.dumps(rec) + "\n")
        sys.stderr.flush()


class UsageMiddleware(Middleware):
    def __init__(self, server: str):
        self.server = server

    async def on_call_tool(self, context, call_next):
        start = time.perf_counter()
        outcome = "error"
        failure = None
        try:
            result = await call_next(context)
            if getattr(result, "is_error", False):
                failure = result
            else:
                outcome = "ok"
            return result
        except BaseException as exc:  # incl. CancelledError: a client timeout is a cause too
            failure = exc
            raise
        finally:
            with suppress(Exception):  # the context lookups can raise too
                emit(
                    self.server,
                    getattr(context.message, "name", "?"),
                    round((time.perf_counter() - start) * 1000),
                    outcome,
                    getattr(
                        getattr(context.fastmcp_context, "request_context", None),
                        "protocol_version",
                        None,
                    ),
                    *(describe(failure) if failure is not None else ()),
                )
