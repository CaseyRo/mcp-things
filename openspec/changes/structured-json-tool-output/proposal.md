## Why

External MCP reviewers (and downstream clients like ChatGPT, n8n, and agentic LLMs) flag that every tool in this server returns only a plain text block: human-readable strings concatenated by `format_todo` / `format_project` / `format_area` / `format_tag`. There is no `structuredContent` payload on the response, so clients cannot reliably read fields (UUIDs, dates, tags, project links) without regex-parsing prose. That blocks chained tool calls, breaks ChatGPT's strict-mode schema expectations on the *response* side, and forces every consumer to re-implement a fragile parser.

FastMCP 3.x natively supports structured tool output: when a tool returns a `ToolResult` (or, for simple cases, a `BaseModel` / `dict` with an annotated return type), the SDK emits a JSON `structuredContent` block alongside a `content` text block and publishes an `outputSchema` in `tools/list`. We should adopt this for all 32 tools so machine consumers get JSON and humans still get readable text.

## What Changes

- Define a uniform JSON envelope for every tool response — `data`, `summary`, `meta` — and Pydantic models for the core domain objects (Todo, Project, Area, Tag, ChecklistItem, WriteResult, BulkResult, ReviewReport, TriageInsights). The envelope deliberately omits `ok`/`isError` (MCP's protocol-level `isError` flag, set by raising `ToolError`, is the source of truth) and folds non-fatal `warnings` into `meta` to avoid a fourth top-level field that would be empty on most calls.
- Update all 32 tools across `tools_gtd_core.py`, `tools_gtd_organize.py`, `tools_gtd_reflect.py`, `tools_utility.py`, `tools_batch.py` to return `ToolResult(content=[TextContent(...)], structured_content=envelope.model_dump())`. The explicit `TextContent` is required because FastMCP's auto-derived text block for a model return is raw JSON — that would regress every text-only client (Claude Desktop's readable view, prompt logs, etc.).
- Refactor `formatters.py`: split each `format_*` into a `to_dict_*` (canonical JSON) and a `render_*` (human text) helper. The `render_*` output goes into the `TextContent`; the `to_dict_*` output goes into `structured_content`. Today's text shape is preserved field-for-field.
- Add a `WriteResult` model (`acknowledged`, `thing_id`, `summary`) for the ~20 write tools (`capture-task`, `complete-task`, `schedule-task`, `delegate-task`, `defer-task`, `modify-*`, `merge-areas`, …) that have no structured `data` today.
- Extend `BulkResult` with per-item fault detail — `succeeded_ids`, `failed_ids`, `errors: dict[str, str]` — so an LLM calling `bulk-complete` learns *which* items failed without a follow-up `get-tasks` call.
- Publish `outputSchema` on every tool registration by passing `output_schema=…` to each `@mcp.tool(...)` decorator. Auto-derivation does not apply when the return type is `ToolResult`, so this kwarg is mandatory per tool.
- Extend `ClientCompatibilityMiddleware.on_list_tools` to apply the existing ChatGPT strict-mode transforms (`additionalProperties: false`, nullable-type expansion, `anyOf` flattening) to output schemas the same way it already does for input schemas. Audit the `anyOf` flattener to confirm it recurses into Pydantic's `$defs` before shipping.
- Add unit tests asserting (a) every tool returns a validated envelope, (b) `structuredContent` round-trips through FastMCP, (c) the `TextContent` block still contains the fields the existing tests check for, (d) `tools/list` advertises an `outputSchema` for every tool, (e) ChatGPT strict-mode transforms produce valid JSON Schema for every tool's output.
- **BREAKING** only for any client that pattern-matches the *exact* current text body. The text block is preserved field-for-field where feasible, but downstream regex consumers should migrate to `structuredContent`. No breaking change for clients that just display the text.

## Capabilities

### New Capabilities

- `structured-tool-output`: defines the three-field JSON envelope (`data`/`summary`/`meta`), the canonical Pydantic models for Things domain objects (Todo, Project, Area, Tag, ChecklistItem, WriteResult, BulkResult, ReviewReport, TriageInsights) including per-item fault detail in `BulkResult`, the contract that every tool must return `ToolResult` with explicit `TextContent` + `structured_content`, the rule that `output_schema=` must be passed to every `@mcp.tool(...)` registration, the use of `ToolError` (mapped to MCP `isError`) for failures instead of an envelope-level `ok` flag, and the `outputSchema` publication + ChatGPT strict-mode transforms applied to output schemas in `on_list_tools`.

### Modified Capabilities

<!-- None. The existing specs (server-auth, server-testing, security-hardening) cover transport auth, test markers, and secret handling — none describe tool response shape, so no delta specs are needed. -->

## Impact

- **Code**: `formatters.py` split into `to_dict_*` (JSON) + `render_*` (text) helpers; new `models.py` (or `schemas.py`) with `ToolEnvelope`, `WriteResult`, `BulkResult`, and the domain models; every `@mcp.tool` function in `tools_gtd_core.py`, `tools_gtd_organize.py`, `tools_gtd_reflect.py`, `tools_utility.py`, `tools_batch.py` updated to return `ToolResult(content=[TextContent(...)], structured_content=envelope.model_dump())` and to declare `output_schema=` on its decorator; `server_core.py` `on_list_tools` extended to transform output schemas (with `anyOf`-flattening verified to recurse into `$defs`); tests under `tests/` updated/added for envelope, `structuredContent`, `TextContent` parity, `outputSchema` advertisement, and strict-mode validity.
- **API surface**: `tools/list` now advertises `outputSchema` per tool; `tools/call` responses now include `structuredContent` plus the existing text content; tool failures continue to surface as MCP `isError: true` via `ToolError`. Wire format remains MCP-compliant.
- **Dependencies**: no new runtime deps (Pydantic and FastMCP 3.x are already in use).
- **Consumers**: Claude Desktop, Claude Code, ChatGPT, n8n, and any other MCP client gain machine-readable output; LLMs can chain tool calls without prose-parsing. Clients that grepped the text body must migrate.
- **Docs**: `CLAUDE.md` (Key Patterns, Client Compatibility Middleware) needs a short section on the envelope and the strict-mode output-schema behaviour.
