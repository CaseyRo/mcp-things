<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# AGENTS

This file tracks the agent's thoughts, ideas, and work flow for the `things-fastmcp` repository.

## Instructions
- Append a new entry under `## Log` for each change made.
- Briefly describe the reasoning behind significant decisions.
- Run `ruff check .` and `pytest` after modifications.

## Log
### 2025-10-11
- Added shared MCP error helper returning `CallToolResult` and updated tool handlers to use it for failure cases.

### 2025-10-11
- Added MCP tool annotations across registration and Fast/Simple server implementations to align with MCP metadata expectations.

### 2025-10-11
- Added CLI flags and env var validation to the run script so operators can easily bind to alternate hosts and ports without manual exports.
- Extended FastMCP server binding logic and README guidance to document the new port override support.
### 2025-10-10
- Added FastMCP constructor introspection for icon support and guarded icon metadata so older runtimes still launch cleanly.

### 2025-10-09
- Added compatibility helper so FastMCP icon metadata works whether or not `mcp.types.Icon` is available in the runtime.
- Guarded FastMCP server construction so `website_url` metadata is only passed when supported by the installed MCP version.

### 2025-10-07
- Implemented logging redaction across handlers and the AppleScript bridge so user task content stays out of logs.
- Removed duplicate binding announcements from the CLI entrypoint so runtime logging only happens once and cached the binding helper for reuse.
- Clarified binding logs and helper exports so launchers surface localhost default without double logging.
- Switched FastMCP server default bind address to localhost with env override and documented exposure steps.
- Added FastMCP metadata (instructions, website, icon) constants and wired them into the server instantiation.
- Documented the surfaced assistant guidance in the README to mirror the MCP experience.
- Converted MCP icon metadata to use `mcp.types.Icon` objects to satisfy FastMCP validation.

### 2025-09-01
- Added `run_things_fastmcp.sh` helper script and integrated Rich logging.
- Documented macOS limitations preventing Docker usage for opening scripts.
- Introduced this AGENTS.md to record ongoing work.

### 2025-09-01
- Updated run script to bootstrap a uv-managed virtual environment or fall back to system Python.
- Clarified Quick Start docs about the helper script's environment handling.

### 2025-10-07
- Added standalone privacy and terms documents so operators understand local data handling and policy expectations.
- Updated README to link to the new policies and prompt users to review them before setup, keeping onboarding aligned with compliance guidance.
