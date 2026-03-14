"""Input validation for Things MCP tools.

Provides validation functions for user-supplied inputs before they reach
AppleScript or other system interfaces.
"""

import re
from typing import List, Optional

from fastmcp.exceptions import ToolError

# Tag names: word chars, spaces, hyphens, @prefix. Reject anything else.
TAG_NAME_PATTERN = re.compile(r"^[@\w\s\-]+$")

# Valid Things list names for show-in-app
VALID_LIST_NAMES = {
    "inbox",
    "today",
    "tomorrow",
    "upcoming",
    "anytime",
    "someday",
    "logbook",
    "trash",
    "deadlines",
    "repeating",
    "all-projects",
    "logged-projects",
}

# Things UUIDs: alphanumeric plus hyphens, typically 10-30 chars
THINGS_UUID_PATTERN = re.compile(r"^[A-Za-z0-9\-_]{6,40}$")


MAX_NAME_LENGTH = 255
MAX_NOTES_LENGTH = 10_000


def validate_name(name: str, field: str = "name") -> None:
    """Validate a name/title input for use in AppleScript or URL scheme.

    Rejects empty/whitespace-only strings and enforces length limits.
    Raises ToolError for invalid input.
    """
    if not name or not name.strip():
        raise ToolError(f"{field} cannot be empty or whitespace-only")
    if len(name) > MAX_NAME_LENGTH:
        raise ToolError(
            f"{field} exceeds maximum length of {MAX_NAME_LENGTH} characters"
        )


def validate_notes_length(notes: str) -> None:
    """Validate notes text length.

    Raises ToolError if notes exceed the maximum length.
    """
    if notes and len(notes) > MAX_NOTES_LENGTH:
        raise ToolError(f"Notes exceed maximum length of {MAX_NOTES_LENGTH} characters")


def validate_tag_names(tags: Optional[List[str]]) -> None:
    """Validate tag names against safe character pattern.

    Raises ToolError if any tag contains characters that could enable
    AppleScript injection.
    """
    if not tags:
        return

    for tag in tags:
        if not TAG_NAME_PATTERN.match(tag):
            raise ToolError(
                f"Invalid tag name: '{tag}'. "
                "Tags may only contain letters, numbers, spaces, hyphens, "
                "underscores, and the @ prefix."
            )


def validate_show_id(id: str) -> None:
    """Validate the id parameter for show-in-app.

    Accepts known list names and Things UUID format.
    Raises ToolError for invalid formats.
    """
    if id in VALID_LIST_NAMES:
        return
    if THINGS_UUID_PATTERN.match(id):
        return
    raise ToolError(
        f"Invalid id: '{id}'. Must be a Things UUID or a known list name: "
        f"{', '.join(sorted(VALID_LIST_NAMES))}"
    )
