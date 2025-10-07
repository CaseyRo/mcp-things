#!/usr/bin/env bash
# Run the Things FastMCP server.
#
# By default the server listens on 127.0.0.1. To expose it beyond the local
# machine export `THINGS_FASTMCP_HOST=0.0.0.0` (or another interface) before
# launching.
#
# If [uv](https://github.com/astral-sh/uv) is installed, this script uses it to
# create (or reuse) a virtual environment and install dependencies. Otherwise
# it falls back to the first available python3/python executable.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v uv >/dev/null 2>&1; then
  # Bootstrap a local virtual environment if it doesn't exist yet
  if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    uv venv "$SCRIPT_DIR/.venv"
    UV_PROJECT_PATH="$SCRIPT_DIR" uv pip install -e "$SCRIPT_DIR"
  fi
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.venv/bin/activate"
  exec python "$SCRIPT_DIR/things_fast_server.py" "$@"
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Error: Python 3 is required. Install uv (pipx install uv) or ensure python3 is on your PATH." >&2
  exit 1
fi
exec "$PYTHON_BIN" "$SCRIPT_DIR/things_fast_server.py" "$@"
