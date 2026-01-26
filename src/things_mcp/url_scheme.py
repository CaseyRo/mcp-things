import json
import logging
import platform
import random
import subprocess
import time
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Union
from .utils import circuit_breaker, rate_limiter, is_things_running

logger = logging.getLogger(__name__)


def launch_things() -> bool:
    """Launch Things app if not already running.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if is_things_running():
            return True

        subprocess.run(
            ["open", "-a", "Things3"], capture_output=True, text=True, check=False
        )

        # Give Things time to launch
        time.sleep(2)

        return is_things_running()
    except Exception as e:
        logger.error(f"Error launching Things: {str(e)}")
        return False


def _open_url_background(url: str) -> bool:
    """Attempt to open a URL without bringing the browser to the foreground.

    Uses ``osascript`` on macOS to execute ``open -g`` so the URL is handled in
    the background. Returns ``True`` if the AppleScript command succeeded,
    otherwise ``False``.
    """
    if platform.system() != "Darwin":
        return False

    try:
        # Use open -g to avoid stealing focus from the foreground application
        script = f'do shell script "open -g \\"{url}\\""'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(f"osascript error: {result.stderr}")
            return False
        return True
    except FileNotFoundError:
        logger.warning("osascript not found; falling back to webbrowser")
        return False
    except Exception as e:
        logger.error(f"Error running osascript: {str(e)}")
        return False


def execute_url(url: str) -> bool:
    """Execute a Things URL by opening it in the default browser.
    Returns True if successful, False otherwise.
    """
    # Ensure any + signs in the URL are replaced with %20
    url = url.replace("+", "%20")

    # Log the URL for debugging
    logger.debug(f"Executing URL: {url}")

    # Apply rate limiting
    rate_limiter.wait_if_needed()

    # Check if circuit breaker allows the operation
    if not circuit_breaker.allow_operation():
        logger.warning("Circuit breaker is open, blocking operation")
        return False

    try:
        # Check if Things is running, attempt to launch if not
        if not is_things_running():
            logger.info("Things is not running, attempting to launch")
            if not launch_things():
                logger.error("Failed to launch Things")
                circuit_breaker.record_failure()
                return False

        # Execute the URL - prefer osascript in the background on macOS
        result = _open_url_background(url)
        if not result:
            result = webbrowser.open(url)

        if not result:
            circuit_breaker.record_failure()
            logger.error(f"Failed to open URL: {url}")
            return False

        # Add a small delay to allow Things time to process the command
        # Add jitter to prevent thundering herd problem
        delay = 0.5 + random.uniform(0, 0.2)  # 0.5-0.7 seconds
        time.sleep(delay)

        circuit_breaker.record_success()
        return True
    except Exception as e:
        logger.error(f"Failed to execute URL: {url}, Error: {str(e)}")
        circuit_breaker.record_failure()
        return False


def execute_xcallback_url(action: str, params: Dict[str, Any]) -> bool:
    """Execute a Things X-Callback-URL.

    Args:
        action: The X-Callback action to perform
        params: Parameters for the action

    Returns:
        bool: True if successful, False otherwise
    """
    # The correct format for Things URLs (no 'x-callback-url/' prefix)
    base_url = "things:///"

    # Add callback parameters, but only if we need them
    # For now, avoid using callbacks since we don't have a handler for them
    callback_params = params.copy()

    # Don't add callback URLs - this avoids the "no application set to open URL" error
    # If we need callbacks later, we'd need to register a URL handler for our app

    # Construct URL - action is part of the path (not a separate query parameter)
    url = f"{base_url}{action}?{urllib.parse.urlencode(callback_params)}"

    # Log the URL for debugging
    logger.debug(f"Executing URL: {url}")

    return execute_url(url)


def construct_url(command: str, params: Dict[str, Any]) -> str:
    """Construct a Things URL from command and parameters."""
    # Use parameters as provided. urllib.parse.quote will handle encoding of
    # spaces and literal plus signs correctly (" " -> "%20", "+" -> "%2B").

    # Start with base URL
    url = f"things:///{command}"

    # Get authentication token if needed - applies to all commands to ensure reliability
    try:
        # Import here to avoid circular imports
        from . import config

        # Get token from config system
        token = config.get_things_auth_token()

        if token:
            # Add token to all params for consistent behavior
            params["auth-token"] = token
            logger.debug(f"Auth token from config used for {command} operation")
        else:
            logger.warning(
                "No Things auth token found in config. URL may not work without a token."
            )
            # Note: We continue without a token, which may cause the operation to fail
    except Exception as e:
        logger.error(f"Error getting auth token: {str(e)}")
        # Continue without token - the operation may fail

    # Disable JSON API for now as it's causing formatting issues
    # JSON API is currently experimental and unreliable
    # We'll use the standard URL scheme instead which is more reliable
    use_json_api = False

    if False and command in ["add"] and use_json_api:
        # This code is disabled but kept for reference
        logger.info("JSON API is currently disabled due to formatting issues")
        pass

    # Standard URL scheme encoding
    if params:
        encoded_params = []
        for key, value in params.items():
            if value is None:
                continue
            # Handle boolean values
            if isinstance(value, bool):
                value = str(value).lower()
            # Handle lists (for tags, checklist items etc)
            elif isinstance(value, list) and key == "tags":
                # Important: Tags are sensitive to formatting in Things URL scheme
                # Based on testing, using a simple comma-separated list without spaces works best
                encoded_tags = []
                for tag in value:
                    # Ensure tag is properly encoded as string
                    tag_str = str(tag).strip()
                    if tag_str:  # Only add non-empty tags
                        encoded_tags.append(tag_str)

                # Only include non-empty tag lists
                if encoded_tags:
                    # Join with commas - Things expects comma-separated tags without spaces between commas
                    # Use a simple comma with no spacing for maximum compatibility
                    value = ",".join(encoded_tags)
                else:
                    # If no valid tags, don't include this parameter
                    continue
            # Handle other lists
            elif isinstance(value, list):
                value = ",".join(str(v) for v in value)

            # Encode the value. urllib.parse.quote will encode spaces as %20 and
            # preserve literal plus signs by converting them to %2B.
            encoded_value = urllib.parse.quote(str(value), safe="")
            encoded_params.append(f"{key}={encoded_value}")

        url += "?" + "&".join(encoded_params)

    logger.debug(f"Constructed Things URL: {url}")
    return url


def should_use_json_api() -> bool:
    """Determine if the JSON API should be used based on Things version."""
    from .utils import detect_things_version

    version = detect_things_version()
    if not version:
        # Default to using JSON API if version can't be determined
        return True

    try:
        # Parse version string (e.g., '3.15.4')
        major, minor, _ = map(int, version.split("."))

        # JSON API is available in Things 3.4+
        return major > 3 or (major == 3 and minor >= 4)
    except Exception:
        # Default to standard URL scheme if version parsing fails
        return False


def add_todo(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[list[str]] = None,
    checklist_items: Optional[list[str]] = None,
    list_id: Optional[str] = None,
    list_title: Optional[str] = None,
    heading: Optional[str] = None,
    completed: Optional[bool] = None,
) -> str:
    """Construct URL to add a new todo."""
    params = {
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "checklist-items": "\n".join(checklist_items) if checklist_items else None,
        "list-id": list_id,
        "list": list_title,
        "heading": heading,
        "completed": completed,
    }

    # Handle tags separately since they need to be comma-separated
    if tags:
        params["tags"] = ",".join(tags)
    return construct_url("add", {k: v for k, v in params.items() if v is not None})


def add_project(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[list[str]] = None,
    area_id: Optional[str] = None,
    area_title: Optional[str] = None,
    todos: Optional[list[str]] = None,
) -> str:
    """Construct URL to add a new project."""
    params = {
        "title": title,
        "notes": notes,
        "when": when,
        "deadline": deadline,
        "area-id": area_id,
        "area": area_title,
        # Change todos to be newline separated
        "to-dos": "\n".join(todos) if todos else None,
    }

    # Handle tags separately since they need to be comma-separated
    if tags:
        params["tags"] = ",".join(tags)

    return construct_url(
        "add-project", {k: v for k, v in params.items() if v is not None}
    )


def update_todo(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    prepend_notes: Optional[str] = None,
    append_notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[Union[list[str], str]] = None,
    add_tags: Optional[Union[list[str], str]] = None,
    checklist_items: Optional[list[str]] = None,
    prepend_checklist_items: Optional[list[str]] = None,
    append_checklist_items: Optional[list[str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
) -> str:
    """Construct URL to update an existing todo.

    Args:
        id: The UUID of the todo to update
        title: New title (replaces existing)
        notes: New notes (replaces existing)
        prepend_notes: Text to add before existing notes
        append_notes: Text to add after existing notes
        when: Schedule date (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD)
        deadline: Deadline date (YYYY-MM-DD)
        tags: Tags to set (replaces existing)
        add_tags: Tags to add without replacing existing ones
        checklist_items: Checklist items (replaces existing)
        prepend_checklist_items: Items to add at beginning of checklist
        append_checklist_items: Items to add at end of checklist
        completed: Mark as completed
        canceled: Mark as canceled
    """
    params = {
        "id": id,
        "title": title,
        "notes": notes,
        "prepend-notes": prepend_notes,
        "append-notes": append_notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "add-tags": add_tags,
        "checklist-items": "\n".join(checklist_items) if checklist_items else None,
        "prepend-checklist-items": "\n".join(prepend_checklist_items)
        if prepend_checklist_items
        else None,
        "append-checklist-items": "\n".join(append_checklist_items)
        if append_checklist_items
        else None,
        "completed": completed,
        "canceled": canceled,
    }
    return construct_url("update", {k: v for k, v in params.items() if v is not None})


def update_project(
    id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    prepend_notes: Optional[str] = None,
    append_notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[Union[list[str], str]] = None,
    add_tags: Optional[Union[list[str], str]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
) -> str:
    """Construct URL to update an existing project.

    Args:
        id: The UUID of the project to update
        title: New title (replaces existing)
        notes: New notes (replaces existing)
        prepend_notes: Text to add before existing notes
        append_notes: Text to add after existing notes
        when: Schedule date
        deadline: Deadline date
        tags: Tags to set (replaces existing)
        add_tags: Tags to add without replacing existing ones
        completed: Mark as completed
        canceled: Mark as canceled
    """
    params = {
        "id": id,
        "title": title,
        "notes": notes,
        "prepend-notes": prepend_notes,
        "append-notes": append_notes,
        "when": when,
        "deadline": deadline,
        "tags": tags,
        "add-tags": add_tags,
        "completed": completed,
        "canceled": canceled,
    }
    return construct_url(
        "update-project", {k: v for k, v in params.items() if v is not None}
    )


def show(
    id: str, query: Optional[str] = None, filter_tags: Optional[list[str]] = None
) -> str:
    """Construct URL to show a specific item or list."""
    params = {"id": id, "query": query, "filter": filter_tags}
    return construct_url("show", {k: v for k, v in params.items() if v is not None})


def search(query: str) -> str:
    """Construct URL to perform a search."""
    return construct_url("search", {"query": query})


# =============================================================================
# JSON API Support for Bulk Operations
# =============================================================================


def build_todo_object(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[list[str]] = None,
    checklist_items: Optional[list[Dict[str, Any]]] = None,
    list_id: Optional[str] = None,
    heading: Optional[str] = None,
    heading_id: Optional[str] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build a to-do object for the JSON API.

    Args:
        title: Task title (required)
        notes: Task notes
        when: Schedule (today, tomorrow, evening, anytime, someday, or date)
        deadline: Deadline date
        tags: List of tag names
        checklist_items: List of checklist item dicts with 'title' and optional 'completed'
        list_id: UUID of project to add to
        heading: Name of heading within project
        heading_id: UUID of heading within project
        completed: Mark as completed
        canceled: Mark as canceled

    Returns:
        Dict suitable for Things JSON API
    """
    attributes: Dict[str, Any] = {"title": title}

    if notes is not None:
        attributes["notes"] = notes
    if when is not None:
        attributes["when"] = when
    if deadline is not None:
        attributes["deadline"] = deadline
    if tags:
        attributes["tags"] = tags
    if checklist_items:
        attributes["checklist-items"] = checklist_items
    if list_id is not None:
        attributes["list-id"] = list_id
    if heading is not None:
        attributes["heading"] = heading
    if heading_id is not None:
        attributes["heading-id"] = heading_id
    if completed is not None:
        attributes["completed"] = completed
    if canceled is not None:
        attributes["canceled"] = canceled

    return {"type": "to-do", "attributes": attributes}


def build_project_object(
    title: str,
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[list[str]] = None,
    area_id: Optional[str] = None,
    area: Optional[str] = None,
    items: Optional[list[Dict[str, Any]]] = None,
    completed: Optional[bool] = None,
    canceled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build a project object for the JSON API.

    Args:
        title: Project title (required)
        notes: Project notes
        when: Schedule
        deadline: Deadline date
        tags: List of tag names
        area_id: UUID of area to add to
        area: Name of area to add to
        items: List of to-do or heading objects to include in project
        completed: Mark as completed
        canceled: Mark as canceled

    Returns:
        Dict suitable for Things JSON API
    """
    attributes: Dict[str, Any] = {"title": title}

    if notes is not None:
        attributes["notes"] = notes
    if when is not None:
        attributes["when"] = when
    if deadline is not None:
        attributes["deadline"] = deadline
    if tags:
        attributes["tags"] = tags
    if area_id is not None:
        attributes["area-id"] = area_id
    if area is not None:
        attributes["area"] = area
    if items:
        attributes["items"] = items
    if completed is not None:
        attributes["completed"] = completed
    if canceled is not None:
        attributes["canceled"] = canceled

    return {"type": "project", "attributes": attributes}


def build_heading_object(title: str, archived: Optional[bool] = None) -> Dict[str, Any]:
    """Build a heading object for the JSON API.

    Args:
        title: Heading title
        archived: Whether the heading is archived

    Returns:
        Dict suitable for Things JSON API
    """
    attributes: Dict[str, Any] = {"title": title}
    if archived is not None:
        attributes["archived"] = archived
    return {"type": "heading", "attributes": attributes}


def build_checklist_item(
    title: str, completed: Optional[bool] = None, canceled: Optional[bool] = None
) -> Dict[str, Any]:
    """Build a checklist item object for the JSON API.

    Args:
        title: Checklist item title
        completed: Whether the item is completed
        canceled: Whether the item is canceled

    Returns:
        Dict suitable for Things JSON API
    """
    attributes: Dict[str, Any] = {"title": title}
    if completed is not None:
        attributes["completed"] = completed
    if canceled is not None:
        attributes["canceled"] = canceled
    return {"type": "checklist-item", "attributes": attributes}


def construct_json_url(items: list[Dict[str, Any]]) -> str:
    """Construct a Things JSON URL for bulk operations.

    Args:
        items: List of to-do, project, or heading objects

    Returns:
        URL string for the Things JSON API
    """
    # Get auth token
    try:
        from . import config

        token = config.get_things_auth_token()
    except Exception:
        token = None

    # Serialize to JSON and URL-encode
    json_data = json.dumps(items, separators=(",", ":"))  # Compact JSON
    encoded_data = urllib.parse.quote(json_data, safe="")

    # Build URL
    url = f"things:///json?data={encoded_data}"
    if token:
        url += f"&auth-token={urllib.parse.quote(token, safe='')}"

    logger.debug(f"Constructed JSON URL with {len(items)} items")
    return url


def execute_json(items: list[Dict[str, Any]]) -> bool:
    """Execute a Things JSON API request for bulk operations.

    Args:
        items: List of to-do, project, or heading objects

    Returns:
        True if successful, False otherwise
    """
    url = construct_json_url(items)
    return execute_url(url)


def add_project_with_tasks(
    title: str,
    tasks: list[Dict[str, Any]],
    notes: Optional[str] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    tags: Optional[list[str]] = None,
    area: Optional[str] = None,
    area_id: Optional[str] = None,
    headings: Optional[Dict[str, list[Dict[str, Any]]]] = None,
) -> str:
    """Construct JSON URL to create a project with tasks atomically.

    This uses the JSON API to create a project and its tasks in a single
    operation, ensuring atomicity.

    Args:
        title: Project title
        tasks: List of task dicts with 'title' and optional other fields
        notes: Project notes
        when: Project schedule
        deadline: Project deadline
        tags: Project tags
        area: Area name to add project to
        area_id: Area UUID to add project to
        headings: Dict mapping heading names to lists of tasks under that heading

    Returns:
        URL string for the Things JSON API
    """
    # Build project items (tasks and headings)
    items: list[Dict[str, Any]] = []

    # Add tasks without headings first
    for task in tasks:
        task_obj = build_todo_object(
            title=task.get("title", ""),
            notes=task.get("notes"),
            when=task.get("when"),
            deadline=task.get("deadline"),
            tags=task.get("tags"),
            checklist_items=[
                build_checklist_item(item) if isinstance(item, str) else item
                for item in task.get("checklist_items", [])
            ]
            if task.get("checklist_items")
            else None,
        )
        items.append(task_obj)

    # Add headings with their tasks
    if headings:
        for heading_name, heading_tasks in headings.items():
            # Add the heading
            items.append(build_heading_object(heading_name))
            # Add tasks under this heading
            for task in heading_tasks:
                task_obj = build_todo_object(
                    title=task.get("title", ""),
                    notes=task.get("notes"),
                    when=task.get("when"),
                    deadline=task.get("deadline"),
                    tags=task.get("tags"),
                )
                items.append(task_obj)

    # Build the project object with all items
    project = build_project_object(
        title=title,
        notes=notes,
        when=when,
        deadline=deadline,
        tags=tags,
        area=area,
        area_id=area_id,
        items=items,
    )

    return construct_json_url([project])
