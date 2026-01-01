#!/usr/bin/env python3
"""Wrapper script to run pytest with proper output handling."""
import sys
import subprocess
import os

if __name__ == "__main__":
    # Write debug info to file to verify script is running
    with open("/tmp/uv_test_debug.log", "w") as f:
        f.write(f"Script started\nPython: {sys.version}\nCWD: {os.getcwd()}\nArgs: {sys.argv}\n")

    # Run pytest directly - uv should handle the environment
    # Use python -m pytest to ensure we use the right pytest
    args = ["python", "-u", "-m", "pytest", "tests"] + sys.argv[1:]

    # Run with real-time output
    result = subprocess.run(args, bufsize=0)
    sys.exit(result.returncode)

