#!/bin/bash
# Wrapper script to run pytest with proper output
# Force unbuffered output and ensure we're in the right directory
cd "$(dirname "$0")" || exit 1
export PYTHONUNBUFFERED=1
exec python -u -m pytest tests "$@"

