#!/bin/bash

# Start Things MCP server via pm2
# Assumes uv is installed and the project is set up
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

pm2 start "uv run server" --interpreter none --name things-mcp
