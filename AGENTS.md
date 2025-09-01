# AGENTS

This file tracks the agent's thoughts, ideas, and work flow for the `things-fastmcp` repository.

## Instructions
- Append a new entry under `## Log` for each change made.
- Briefly describe the reasoning behind significant decisions.
- Run `ruff check .` and `pytest` after modifications.

## Log
### 2025-09-01
- Added `run_things_fastmcp.sh` helper script and integrated Rich logging.
- Documented macOS limitations preventing Docker usage for opening scripts.
- Introduced this AGENTS.md to record ongoing work.

### 2025-09-01
- Updated run script to bootstrap a uv-managed virtual environment or fall back to system Python.
- Clarified Quick Start docs about the helper script's environment handling.

### 2025-09-02
- Reinstall dependencies on every run to avoid stale virtual environments missing new packages.
