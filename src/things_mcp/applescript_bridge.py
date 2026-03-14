#!/usr/bin/env python3
import re
import subprocess
import logging
from typing import Dict, Any, Union

from .settings import get_settings

logger = logging.getLogger(__name__)


def _script_metadata(command: str, script: str) -> Dict[str, Any]:
    """Return metadata about an AppleScript command without exposing content."""
    return {
        "command": command,
        "line_count": len(script.splitlines()),
        "char_count": len(script),
    }


def _wrap_script_for_background(script: str) -> str:
    """Wrap AppleScript commands targeting Things3 with 'without activating' to prevent foreground activation.

    Note: 'without activating' is not valid AppleScript syntax in tell blocks, so this function
    currently returns the script unchanged. Background execution prevention would need to be
    handled at the osascript level or through other means.

    Args:
        script: The AppleScript code to potentially wrap

    Returns:
        The original script (wrapping disabled due to syntax limitations)
    """
    # Check if background execution is disabled via settings
    if get_settings().things_mcp_disable_background_osascript:
        logger.debug("Background execution disabled via settings")
        return script

    # NOTE: 'without activating' is not valid AppleScript syntax in tell blocks
    # The syntax causes errors: "Expected end of line but found 'without'"
    # For now, return the script unchanged. Background execution would need
    # to be handled differently (e.g., using osascript flags or other methods)

    # Check if script targets Things3 - log for debugging but don't modify
    if 'tell application "Things3"' in script or 'tell application "Things"' in script:
        logger.debug(
            "Script targets Things3 (background execution wrapping disabled due to syntax limitations)"
        )

    return script


def run_applescript(script: str) -> Union[str, bool]:
    """Run an AppleScript command and return the result.

    Automatically wraps commands targeting Things3 with 'without activating' to prevent
    the application from appearing in the foreground, unless disabled via the
    THINGS_MCP_DISABLE_BACKGROUND_OSASCRIPT environment variable.

    Args:
        script: The AppleScript code to execute

    Returns:
        The result of the AppleScript execution, or False if it failed
    """
    try:
        # Wrap script for background execution if targeting Things3
        wrapped_script = _wrap_script_for_background(script)

        # Use stdin for multi-line scripts (osascript -e only works for single-line)
        # Check if script has newlines
        if "\n" in wrapped_script:
            result = subprocess.run(
                ["osascript"], input=wrapped_script, capture_output=True, text=True
            )
        else:
            result = subprocess.run(
                ["osascript", "-e", wrapped_script], capture_output=True, text=True
            )

        if result.returncode != 0:
            stderr_output = result.stderr or ""
            logger.error(
                "AppleScript process returned error",
                extra={
                    "returncode": result.returncode,
                    "stderr_length": len(stderr_output),
                },
            )
            return False

        return result.stdout.strip()
    except Exception:
        logger.exception("Error running AppleScript")
        return False


def escape_applescript_string(text: str) -> str:
    """Escape special characters in an AppleScript string.

    Strips control characters (null bytes, newlines, tabs, etc.) that could
    break AppleScript structure, then escapes quotes by doubling them.

    Args:
        text: The string to escape

    Returns:
        The escaped string safe for interpolation into AppleScript string literals
    """
    if not text:
        return ""

    # Strip control characters that could break AppleScript structure
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", text)

    # Escape quotes by doubling them (AppleScript style)
    return cleaned.replace('"', '""')
