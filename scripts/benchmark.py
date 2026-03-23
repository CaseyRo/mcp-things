#!/usr/bin/env python3
"""
Benchmark harness for the Things MCP server.

Measures latency of standard MCP tool calls over streamable-http transport.
Reports cold/warm stats with min/avg/p95/max per operation.

Usage:
    uv run python scripts/benchmark.py                          # Markdown output
    uv run python scripts/benchmark.py --output json            # JSON output
    uv run python scripts/benchmark.py --server http://host/mcp # Custom server
    uv run python scripts/benchmark.py --iterations 10          # More iterations
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SERVER = "http://localhost:8009/mcp"
DEFAULT_ITERATIONS = 5
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

SUITE: list[dict[str, Any]] = [
    {"name": "get-tasks (inbox)", "tool": "get-tasks", "args": {"view": "inbox"}},
    {"name": "get-tasks (today)", "tool": "get-tasks", "args": {"view": "today"}},
    {"name": "search-tasks", "tool": "search-tasks", "args": {"query": "test"}},
    {"name": "focus-mode", "tool": "focus-mode", "args": {}},
    {"name": "daily-review", "tool": "daily-review", "args": {}},
]

SCALING_OP = {"name": "get-tasks (all)", "tool": "get-tasks", "args": {}}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class OperationResult:
    name: str
    cold_ms: float
    warm_ms: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def all_ms(self) -> list[float]:
        return [self.cold_ms] + self.warm_ms

    def percentile(self, latencies: list[float], p: float) -> float:
        if not latencies:
            return 0.0
        sorted_l = sorted(latencies)
        k = (len(sorted_l) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_l):
            return sorted_l[-1]
        return sorted_l[f] + (k - f) * (sorted_l[c] - sorted_l[f])

    def stats(self, latencies: list[float]) -> dict[str, float]:
        if not latencies:
            return {"min": 0, "avg": 0, "p95": 0, "max": 0}
        return {
            "min": min(latencies),
            "avg": statistics.mean(latencies),
            "p95": self.percentile(latencies, 95),
            "max": max(latencies),
        }

    def cold_stats(self) -> dict[str, float]:
        return {
            "min": self.cold_ms,
            "avg": self.cold_ms,
            "p95": self.cold_ms,
            "max": self.cold_ms,
        }

    def warm_stats(self) -> dict[str, float]:
        return self.stats(self.warm_ms)

    def overall_stats(self) -> dict[str, float]:
        return self.stats(self.all_ms)


# ---------------------------------------------------------------------------
# MCP JSON-RPC client
# ---------------------------------------------------------------------------


class MCPClient:
    """Minimal MCP streamable-http client using JSON-RPC 2.0."""

    def __init__(self, server_url: str, api_key: str, timeout: float = 30.0):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session_id: str | None = None
        self._request_id = 0
        self._http = httpx.Client(timeout=timeout)

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _post(self, payload: dict) -> dict:
        """Send a JSON-RPC request and return the parsed response."""
        resp = self._http.post(self.server_url, json=payload, headers=self._headers())
        resp.raise_for_status()

        # Capture session ID from response headers
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid

        content_type = resp.headers.get("content-type", "")

        # Handle SSE response (text/event-stream)
        if "text/event-stream" in content_type:
            return self._parse_sse(resp.text)

        # Plain JSON
        return resp.json()

    @staticmethod
    def _parse_sse(text: str) -> dict:
        """Extract the last JSON-RPC result from an SSE stream."""
        result: dict = {}
        for line in text.splitlines():
            if line.startswith("data: "):
                try:
                    result = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
        return result

    def initialize(self) -> dict:
        """Send MCP initialize handshake."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "things-mcp-benchmark", "version": "1.0.0"},
            },
        }
        result = self._post(payload)

        # Send initialized notification
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        self._http.post(self.server_url, json=notif, headers=self._headers())
        return result

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Call an MCP tool and return the full JSON-RPC response."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        return self._post(payload)

    def close(self):
        self._http.close()


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def run_operation(
    client: MCPClient, tool: str, args: dict, iterations: int
) -> tuple[float, list[float], str | None]:
    """Run a tool N times; return (cold_ms, warm_ms_list, error_or_none)."""
    cold_ms = 0.0
    warm_ms: list[float] = []
    error: str | None = None

    for i in range(iterations):
        start = time.perf_counter()
        try:
            resp = client.call_tool(tool, args)
            elapsed = (time.perf_counter() - start) * 1000.0

            # Check for JSON-RPC error
            if "error" in resp:
                error = resp["error"].get("message", str(resp["error"]))
                if i == 0:
                    cold_ms = elapsed
                else:
                    warm_ms.append(elapsed)
                break
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            error = str(exc)
            if i == 0:
                cold_ms = elapsed
            else:
                warm_ms.append(elapsed)
            break

        if i == 0:
            cold_ms = elapsed
        else:
            warm_ms.append(elapsed)

    return cold_ms, warm_ms, error


def run_benchmark(server_url: str, api_key: str, iterations: int) -> dict:
    """Run the full benchmark suite and return structured results."""
    client = MCPClient(server_url, api_key)

    # Initialize session
    print("Initializing MCP session...", file=sys.stderr)
    try:
        init_resp = client.initialize()
        if "error" in init_resp:
            print(f"Initialize error: {init_resp['error']}", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"Failed to connect to {server_url}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Session established. Running {iterations} iterations per operation.\n",
        file=sys.stderr,
    )

    results: list[OperationResult] = []

    # Standard suite
    for op in SUITE:
        print(f"  Benchmarking: {op['name']}...", file=sys.stderr)
        cold, warm, err = run_operation(client, op["tool"], op["args"], iterations)
        r = OperationResult(name=op["name"], cold_ms=cold, warm_ms=warm, error=err)
        results.append(r)
        if err:
            print(f"    Error: {err}", file=sys.stderr)

    # Task count scaling
    print(f"  Benchmarking: {SCALING_OP['name']} (scaling)...", file=sys.stderr)
    cold, warm, err = run_operation(
        client, SCALING_OP["tool"], SCALING_OP["args"], iterations
    )
    scaling_result = OperationResult(
        name=SCALING_OP["name"], cold_ms=cold, warm_ms=warm, error=err
    )
    results.append(scaling_result)

    client.close()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server": server_url,
        "iterations": iterations,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _fmt_ms(v: float) -> str:
    if v >= 1000:
        return f"{v / 1000:.2f}s"
    return f"{v:.1f}ms"


def format_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Things MCP Benchmark Results")
    lines.append("")
    lines.append(f"- **Server:** {data['server']}")
    lines.append(f"- **Timestamp:** {data['timestamp']}")
    lines.append(f"- **Iterations:** {data['iterations']}")
    lines.append("")

    # Overall table
    lines.append("## Overall Latency")
    lines.append("")
    lines.append("| Operation | Min | Avg | P95 | Max | Error |")
    lines.append("|-----------|-----|-----|-----|-----|-------|")
    for r in data["results"]:
        s = r.overall_stats()
        err = r.error or ""
        lines.append(
            f"| {r.name} | {_fmt_ms(s['min'])} | {_fmt_ms(s['avg'])} "
            f"| {_fmt_ms(s['p95'])} | {_fmt_ms(s['max'])} | {err} |"
        )
    lines.append("")

    # Cold vs warm
    lines.append("## Cold vs Warm Latency")
    lines.append("")
    lines.append("| Operation | Cold | Warm Avg | Warm P95 | Warm Max |")
    lines.append("|-----------|------|----------|----------|----------|")
    for r in data["results"]:
        ws = r.warm_stats()
        lines.append(
            f"| {r.name} | {_fmt_ms(r.cold_ms)} | {_fmt_ms(ws['avg'])} "
            f"| {_fmt_ms(ws['p95'])} | {_fmt_ms(ws['max'])} |"
        )
    lines.append("")

    # Scaling note
    scaling = data["results"][-1]
    lines.append("## Task Count Scaling")
    lines.append("")
    lines.append(
        f"`get-tasks` with no view filter (all tasks): avg {_fmt_ms(scaling.overall_stats()['avg'])}"
    )
    lines.append("")

    return "\n".join(lines)


def format_json(data: dict) -> str:
    ops = []
    for r in data["results"]:
        ops.append(
            {
                "name": r.name,
                "cold_ms": round(r.cold_ms, 2),
                "warm_ms": [round(w, 2) for w in r.warm_ms],
                "all_ms": [round(a, 2) for a in r.all_ms],
                "cold_stats": {k: round(v, 2) for k, v in r.cold_stats().items()},
                "warm_stats": {k: round(v, 2) for k, v in r.warm_stats().items()},
                "overall_stats": {k: round(v, 2) for k, v in r.overall_stats().items()},
                "error": r.error,
            }
        )

    output = {
        "timestamp": data["timestamp"],
        "server": data["server"],
        "iterations": data["iterations"],
        "operations": ops,
    }
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def load_api_key() -> str:
    """Load THINGS_MCP_API_KEY from .env file."""
    if not ENV_PATH.exists():
        print(f"Error: .env file not found at {ENV_PATH}", file=sys.stderr)
        sys.exit(1)
    env = dotenv_values(ENV_PATH)
    key = env.get("THINGS_MCP_API_KEY")
    if not key:
        print("Error: THINGS_MCP_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return key


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark harness for Things MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  uv run python scripts/benchmark.py\n"
        "  uv run python scripts/benchmark.py --output json\n"
        "  uv run python scripts/benchmark.py --iterations 10 --server http://host:8009/mcp\n",
    )
    parser.add_argument(
        "--output",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"MCP server URL (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Iterations per operation (default: {DEFAULT_ITERATIONS})",
    )
    args = parser.parse_args()

    api_key = load_api_key()

    data = run_benchmark(args.server, api_key, args.iterations)

    if args.output == "json":
        print(format_json(data))
    else:
        print(format_markdown(data))


if __name__ == "__main__":
    main()
