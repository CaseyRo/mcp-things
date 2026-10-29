# Development

How to work on the code. For how the pieces fit together, read
[architecture.md](architecture.md) first.

## Setup

```bash
git clone https://github.com/CaseyRo/mcp-things.git
cd mcp-things
uv sync
uv run python scripts/configure_token.py   # only needed for real tests and manual runs
```

macOS, Things 3, Python 3.12+ and uv. The default branch is `source`.

## Everyday commands

```bash
uv run pytest                           # CI-safe suite, excludes tests that need Things
uv run python -m pytest tests -m real   # real integration tests, Things 3 required
uv run ruff check . && uv run ruff format .
uv run python scripts/gen_tools_doc.py  # refresh the tool reference in docs/tools.md
```

Run a test server on another port (`THINGS_MCP_PORT=8019 uv run server`) if one
is already running on 8009.

## Adding or changing a tool

Tools are grouped by GTD stage: `tools_gtd_core.py` (Engage, Capture,
Clarify), `tools_gtd_organize.py`, `tools_gtd_reflect.py`, `tools_utility.py`,
`tools_batch.py`.

```python
@mcp.tool(
    name="kebab-case-name",
    annotations=TOOL_ANNOTATIONS["kebab-case-name"],
    tags=tags_for("kebab-case-name"),
    timeout=5,  # 30 for write tools
    output_schema=output_schema_for(ToolEnvelope[list[Todo]]),
)
async def tool_name(param: str, optional_param: str | None = None, ctx: Context = None) -> ToolResult:
    """One line on what it does.

    GTD Stage: Capture|Clarify|Organize|Reflect|Engage
    Use when: the user intents this tool handles
    Instead use: another tool, if a different situation
    """
    return make_result(data, summary="One-sentence headline")
```

- `output_schema=` is mandatory; return a `ToolResult` from `make_result`, `write_result` or `bulk_result`.
- Fail with `raise ToolError("what went wrong and what to try")`. A returned error payload is logged as a success.
- Annotations are snake_case (`read_only_hint`, `destructive_hint`); CI fails on camelCase.
- Cache reads with `@cached(ttl=CACHE_TTL.get("name", 30))`; writes must invalidate what they change.
- Call `ensure_tags_exist(tags)` before writing tags.
- Batch tools are `bulk-*`, take Pydantic item models and validate UUIDs with `validate_uuid_list()`.
- Log with `get_logger(__name__)`. Never log task titles, notes or other user content.
- The description is the tool's interface to the model: say when to use it and when not to.
- Run `scripts/gen_tools_doc.py` so `docs/tools.md` matches.

## Tests

See [TESTING.md](TESTING.md). In short:

| Marker | What | Runs in CI |
|---|---|---|
| `unit` | Mocked dependencies | yes |
| `integration` | May start a server, no Things | yes |
| `real` | Needs Things 3 and a token | no |
| `slow` | Long-running | yes |

Real tests create items prefixed `MCP-TEST-` and clean them up.

## Planning changes with OpenSpec

New tools, breaking changes and architecture work start as an OpenSpec change:

```bash
openspec list                           # active changes
openspec list --specs                   # current capabilities
openspec validate <change-id> --strict
```

A change lives in `openspec/changes/<change-id>/` with `proposal.md`,
`tasks.md`, optional `design.md` and `specs/<capability>/spec.md`. See
`openspec/project.md` for conventions.

## CI and releases

- CI (`.github/workflows/ci.yml`) runs `pip-audit`, ruff and the CI-safe tests as the `test`
  check, which must pass before a pull request merges into `source`.
- Releases are git tags only. After a merge, the release workflow runs the tests, then pushes
  the next `v*` patch tag. Never bump `version` in `pyproject.toml`.
- Not published to PyPI.

## Vendored code

`src/things_mcp/usage.py` is copied verbatim from the CDIT fleet's usage
middleware. Don't edit it here.
