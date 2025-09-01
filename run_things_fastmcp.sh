#!/usr/bin/env bash
# Simple helper to run the Things FastMCP server.
# Uses the current Python environment.
set -e
python "$(dirname "$0")/things_fast_server.py"
