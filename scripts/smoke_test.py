#!/usr/bin/env python3
"""
Smoke test for Things MCP server.

This script performs a quick integration test to verify:
1. Things 3 is available
2. Can read inbox (via get-tasks)
3. Can create a todo (via capture-task)
4. Can update the todo (via modify-task)
5. Can complete the todo (via complete-task)

Run manually: uv run python scripts/smoke_test.py
Used by pre-commit hook to catch issues before committing.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from things_mcp.utils import is_things_running
from things_mcp.fast_server import mcp


# Helper to get tool function from FastMCP
def _get_tool_fn(name: str):
    return mcp._local_provider._components[f"tool:{name}@"].fn


# Get tool functions from the registered GTD tools
get_tasks = _get_tool_fn("get-tasks")
capture_task = _get_tool_fn("capture-task")
modify_task = _get_tool_fn("modify-task")
complete_task = _get_tool_fn("complete-task")


def check_things_available():
    """Check if Things 3 is running."""
    if not is_things_running():
        print("SKIP: Things 3 is not running")
        print("Smoke test requires Things 3 to be running.")
        print("Start Things 3 or set SKIP_SMOKE_TEST=1 to skip.")
        # Exit with 0 to not block commits when Things isn't available
        # In CI, this allows the test to be skipped gracefully
        import os

        if os.environ.get("SKIP_SMOKE_TEST") == "1":
            print("SKIP_SMOKE_TEST=1 set, skipping smoke test")
            sys.exit(0)
        # On local machines, we'll still skip but warn
        print("WARNING: Skipping smoke test (Things 3 not running)")
        sys.exit(0)
    print("OK: Things 3 is running")


async def test_read_inbox():
    """Test reading the inbox via get-tasks."""
    print("Testing: Read inbox...")
    result = await get_tasks(view="inbox")
    if "Error" in result or "error" in result.lower():
        print(f"FAIL: Could not read inbox: {result}")
        return False
    print("OK: Read inbox successfully")
    return True


async def test_create_todo():
    """Test creating a todo via capture-task and return its title."""
    print("Testing: Create todo...")
    # Use a unique title to avoid conflicts
    title = f"SMOKE-TEST-{int(time.time())}"

    result = await capture_task(
        title=title,
        notes="Smoke test - will be deleted automatically",
    )

    if "Captured to Inbox" not in result:
        print(f"FAIL: Could not create todo: {result}")
        return None

    print(f"OK: Created todo '{title}'")
    return title


async def find_todo_id(title: str, max_retries: int = 3):
    """Find a todo by title and return its ID."""
    import things

    for attempt in range(max_retries):
        # Search for the todo
        search_results = things.search(title)
        for item in search_results:
            if item.get("type") == "to-do" and item.get("title") == title:
                return item["uuid"]

        # Check inbox
        inbox_todos = things.inbox()
        for todo in inbox_todos:
            if todo.get("title") == title:
                return todo["uuid"]

        # Check today
        today_todos = things.today()
        for todo in today_todos:
            if todo.get("title") == title:
                return todo["uuid"]

        if attempt < max_retries - 1:
            time.sleep(0.5)

    return None


async def test_update_todo(title: str):
    """Test updating a todo via modify-task."""
    print("Testing: Update todo...")

    # Find the todo ID
    todo_id = await find_todo_id(title)
    if not todo_id:
        print(f"FAIL: Could not find todo '{title}' to update")
        return False

    # Update it
    result = await modify_task(
        task_id=todo_id,
        notes="Smoke test - updated notes",
    )

    if "Updated" not in result and "updated" not in result.lower():
        print(f"FAIL: Could not update todo: {result}")
        return False

    print("OK: Updated todo")
    return True


async def test_complete_todo(title: str):
    """Test completing a todo via complete-task."""
    print("Testing: Complete todo...")

    # Find the todo ID
    todo_id = await find_todo_id(title)
    if not todo_id:
        print(f"FAIL: Could not find todo '{title}' to complete")
        return False

    # Complete it
    result = await complete_task(task_id=todo_id)

    if "completed" not in result.lower():
        print(f"FAIL: Could not complete todo: {result}")
        return False

    print("OK: Completed todo")
    return True


async def run_smoke_tests():
    """Run all smoke tests."""
    print("=" * 50)
    print("Things MCP Smoke Test")
    print("=" * 50)

    # Check Things is available
    check_things_available()

    # Run tests
    all_passed = True

    # Test 1: Read inbox
    if not await test_read_inbox():
        all_passed = False

    # Test 2: Create todo
    title = await test_create_todo()
    if not title:
        all_passed = False
    else:
        # Give Things time to process
        time.sleep(1)

        # Test 3: Update todo
        if not await test_update_todo(title):
            all_passed = False

        time.sleep(0.5)

        # Test 4: Complete todo
        if not await test_complete_todo(title):
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("SMOKE TEST PASSED")
        return 0
    else:
        print("SMOKE TEST FAILED")
        return 1


def main():
    """Main entry point."""
    try:
        exit_code = asyncio.run(run_smoke_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
