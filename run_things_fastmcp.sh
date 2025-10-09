#!/usr/bin/env bash
# Run the Things FastMCP server.
#
# By default the server listens on 127.0.0.1:8009. To expose it beyond the local
# machine export `THINGS_FASTMCP_HOST=0.0.0.0` (or another interface) or pass
# `--host 0.0.0.0`. To run on a different port export `THINGS_FASTMCP_PORT` or
# use `--port 9000` (for example).
#
# If [uv](https://github.com/astral-sh/uv) is installed, this script uses it to
# create (or reuse) a virtual environment and install dependencies. Otherwise
# it falls back to the first available python3/python executable.
set -euo pipefail

HOST_OVERRIDE="${THINGS_FASTMCP_HOST:-}"
PORT_OVERRIDE="${THINGS_FASTMCP_PORT:-}"

print_usage() {
  cat <<'USAGE'
Usage: run_things_fastmcp.sh [--host HOST] [--port PORT] [--] [PYTHON_ARGS...]

Options:
  --host HOST    Bind the FastMCP server to the specified interface.
                 (Defaults to 127.0.0.1. Use 0.0.0.0 to listen on all interfaces.)
  --port PORT    Serve the FastMCP server on the specified TCP port (default 8009).
  -h, --help     Show this help text and exit.

Any additional arguments after `--` are forwarded to the Python entrypoint.
Environment variables THINGS_FASTMCP_HOST and THINGS_FASTMCP_PORT override the
defaults and are updated when using the corresponding flags.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ $# -lt 2 ]]; then
        echo "Error: --host requires a value" >&2
        exit 1
      fi
      HOST_OVERRIDE="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "Error: --port requires a value" >&2
        exit 1
      fi
      PORT_OVERRIDE="$2"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ -n "$PORT_OVERRIDE" ]]; then
  if [[ ! "$PORT_OVERRIDE" =~ ^[0-9]+$ ]]; then
    echo "Error: THINGS_FASTMCP_PORT/--port must be an integer" >&2
    exit 1
  fi
  export THINGS_FASTMCP_PORT="$PORT_OVERRIDE"
fi

if [[ -n "$HOST_OVERRIDE" ]]; then
  export THINGS_FASTMCP_HOST="$HOST_OVERRIDE"
fi

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
