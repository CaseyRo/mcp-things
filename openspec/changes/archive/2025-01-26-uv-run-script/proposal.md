## Why

The current bash script (`run_things_fastmcp.sh`) adds unnecessary complexity and maintenance overhead. It handles argument parsing, environment variable management, and virtual environment setup that can be better handled by UV's native capabilities. UV is already the preferred Python package manager for this project and provides built-in support for running scripts with proper dependency management.

## What Changes

- **REMOVED**: `run_things_fastmcp.sh` bash script
- **ADDED**: UV script configuration in `pyproject.toml` for server execution
- **ADDED**: dotenv support for environment variable configuration via `.env` file
- **ADDED**: `.env.example` file with default configuration values
- **MODIFIED**: Documentation to reflect new UV-based execution approach
- **SIMPLIFIED**: Server startup process - users can now run `uv run server` instead of `./run_things_fastmcp.sh`
- **NOTE**: Port configuration via `THINGS_MCP_HOST` and `THINGS_MCP_PORT` environment variables continues to work unchanged

## Impact

- **Affected specs**: Server execution capability
- **Affected code**:
  - `run_things_fastmcp.sh` (deletion)
  - `pyproject.toml` (addition of UV scripts)
  - `README.md` (updated instructions)
- **Breaking change**: Users will need to update their execution commands
- **Simplified maintenance**: No more bash script to maintain, UV handles all dependency management
