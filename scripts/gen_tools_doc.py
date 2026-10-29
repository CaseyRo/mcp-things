"""Regenerate the tool reference section of docs/tools.md from the live tool schemas.

    uv run python scripts/gen_tools_doc.py

Rewrites everything between the GENERATED markers in docs/tools.md, so tool
descriptions and parameters in the docs always match what clients see.
"""

import asyncio
import os
import re
from pathlib import Path

os.environ.setdefault(
    "THINGS_MCP_API_KEY", "tmcp_docs"
)  # keep startup from writing .env

from fastmcp import Client

from things_mcp.fast_server import mcp

DOC = Path(__file__).resolve().parent.parent / "docs" / "tools.md"
BEGIN, END = "<!-- GENERATED:tools -->", "<!-- /GENERATED:tools -->"
STAGES = ["Capture", "Clarify", "Organize", "Reflect", "Engage", "Utility", "Batch"]


def stage_of(name: str, desc: str) -> str:
    if name.startswith("bulk-"):
        return "Batch"
    m = re.search(r"GTD Stage:\s*(\w+)", desc)
    return m.group(1) if m and m.group(1) in STAGES else "Utility"


def one_line(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def render(tools) -> str:
    out = []
    for stage in STAGES:
        group = [t for t in tools if stage_of(t.name, t.description or "") == stage]
        if not group:
            continue
        out.append(f"## {stage}\n")
        for t in group:
            desc = re.sub(r"^\[[^\]]+\]\s*", "", t.description or "")
            summary = desc.split("\n\n")[0].strip()
            use = re.search(r"Use when:\s*(.+)", desc)
            out.append(f"### `{t.name}`\n\n{one_line(summary)}\n")
            if use:
                out.append(f"*Use when:* {one_line(use.group(1))}\n")
            schema = t.input_schema
            props, req = schema.get("properties", {}), set(schema.get("required", []))
            if props:
                out.append("| Parameter | Required | Description |\n|---|---|---|")
                for k, v in props.items():
                    yes = "yes" if k in req else ""
                    out.append(
                        f"| `{k}` | {yes} | {one_line(v.get('description') or '')} |"
                    )
                out.append("")
    return "\n".join(out).rstrip() + "\n"


async def main() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    text = DOC.read_text()
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    DOC.write_text(f"{head}{BEGIN}\n\n{render(tools)}\n{END}{tail}")
    print(f"{len(tools)} tools written to {DOC}")


if __name__ == "__main__":
    asyncio.run(main())
