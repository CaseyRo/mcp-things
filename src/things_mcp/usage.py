"""Canonical MCP usage-telemetry middleware. Vendor this file into each fleet server.

One JSON line per tool call on stderr (stdout would corrupt stdio transports):
    {"mcp_usage": 1, "ts": "...", "server": "siyuan", "tool": "get_block", "duration_ms": 42, "outcome": "ok"}

No arguments, no results. A failure inside telemetry never touches the call.
Works unchanged on fastmcp 3.x and 4.x (`on_call_tool` is the same hook).

Register:  mcp.add_middleware(UsageMiddleware("siyuan"))
Spec:      openspec/changes/upgrade-fleet-fastmcp-4/specs/mcp-usage-telemetry/spec.md
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

from fastmcp.server.middleware import Middleware


class UsageMiddleware(Middleware):
    def __init__(self, server: str):
        self.server = server

    async def on_call_tool(self, context, call_next):
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await call_next(context)
            outcome = "error" if getattr(result, "is_error", False) else "ok"
            return result
        finally:
            try:
                sys.stderr.write(json.dumps({
                    "mcp_usage": 1,
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "server": self.server,
                    "tool": getattr(context.message, "name", "?"),
                    "duration_ms": round((time.perf_counter() - start) * 1000),
                    "outcome": outcome,
                }) + "\n")
                sys.stderr.flush()
            except Exception:
                pass
