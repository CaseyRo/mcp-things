#!/usr/bin/env python3
"""
Tag handler for Things MCP.
Ensures tags exist before applying them.
"""

import logging
from typing import List
from .applescript_bridge import run_applescript, escape_applescript_string

logger = logging.getLogger(__name__)


def ensure_tags_exist(tags: List[str]) -> bool:
    """
    Ensure all tags exist in Things before using them.
    Creates missing tags using AppleScript.

    Args:
        tags: List of tag names to ensure exist

    Returns:
        bool: True if all tags exist or were created successfully
    """
    if not tags:
        return True

    try:
        # Build AppleScript to check and create tags
        script_lines = ['tell application "Things3"']

        for tag in tags:
            # Escape quotes using AppleScript convention (doubled quotes)
            escaped_tag = escape_applescript_string(tag)

            # Check if tag exists, create if not
            script_lines.extend(
                [
                    f'  set tagName to "{escaped_tag}"',
                    "  set tagExists to false",
                    "  repeat with t in tags",
                    "    if name of t is tagName then",
                    "      set tagExists to true",
                    "      exit repeat",
                    "    end if",
                    "  end repeat",
                    "  if not tagExists then",
                    "    try",
                    "      make new tag with properties {name:tagName}",
                    '      log "Created tag: " & tagName',
                    "    on error",
                    '      log "Failed to create tag: " & tagName',
                    "    end try",
                    "  end if",
                ]
            )

        script_lines.append("end tell")
        script = "\n".join(script_lines)

        # Execute the AppleScript using run_applescript for background execution support
        # Note: 'without activating' will be automatically added by run_applescript()
        result = run_applescript(script)

        if not result:
            logger.error("Failed to ensure tags exist")
            return False

        logger.info(f"Ensured tags exist: {', '.join(tags)}")
        return True

    except Exception as e:
        logger.error(f"Error ensuring tags exist: {str(e)}")
        return False


def get_existing_tags() -> List[str]:
    """
    Get list of all existing tags in Things.

    Returns:
        List[str]: List of tag names
    """
    try:
        script = """tell application "Things3"
            set tagList to {}
            repeat with t in tags
                set end of tagList to name of t
            end repeat
            return tagList
        end tell"""

        # Execute the AppleScript using run_applescript for background execution support
        # Note: 'without activating' will be automatically added by run_applescript()
        result = run_applescript(script)

        if result:
            # Parse the output (comma-separated list)
            # result is already a string from run_applescript
            tags = [tag.strip() for tag in str(result).strip().split(",")]
            return tags

        return []

    except Exception as e:
        logger.error(f"Error getting existing tags: {str(e)}")
        return []
