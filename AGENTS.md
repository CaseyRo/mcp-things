# AGENTS

This file tracks the agent's thoughts, ideas, and work flow for the `things-fastmcp` repository.

## Instructions
- Append a new entry under `## Log` for each change made.
- Briefly describe the reasoning behind significant decisions.
- Run `ruff check .` and `pytest` after modifications.

## Log
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
