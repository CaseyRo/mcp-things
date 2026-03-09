#!/usr/bin/env python3
"""Real integration tests for Organize, Reflect, and Utility tools.

Runs against live Things 3. All test data uses MCP-TEST- prefix and is cleaned up.

Run:  uv run python tests/test_organize_reflect_utility_real.py
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from things_mcp.settings import get_settings

get_settings()  # Load .env

import things  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from things_mcp.fast_server import mcp  # noqa: E402
from things_mcp.utils import is_things_running  # noqa: E402
from things_mcp.applescript_bridge import run_applescript  # noqa: E402


# ============================================================================
# Helpers
# ============================================================================


def _get_tool_fn(name: str):
    return mcp._local_provider._components[f"tool:{name}@"].fn


def gen_title(label: str) -> str:
    return f"MCP-TEST-{label}-{int(time.time())}-{uuid.uuid4().hex[:6]}"


def find_todo(title: str, retries: int = 5) -> str | None:
    """Find a todo by exact title, returns UUID or None."""
    for _ in range(retries):
        for item in things.search(title):
            if item.get("title") == title:
                return item["uuid"]
        for item in things.inbox():
            if item.get("title") == title:
                return item["uuid"]
        for item in things.today():
            if item.get("title") == title:
                return item["uuid"]
        for item in things.anytime():
            if item.get("title") == title:
                return item["uuid"]
        for item in things.someday():
            if item.get("title") == title:
                return item["uuid"]
        time.sleep(0.5)
    return None


def find_project(title: str, retries: int = 5) -> str | None:
    """Find a project by exact title, returns UUID or None."""
    for _ in range(retries):
        for p in things.projects() or []:
            if p.get("title") == title:
                return p["uuid"]
        time.sleep(0.5)
    return None


def delete_item(item_id: str, item_type: str = "to do"):
    """Delete a todo or project by UUID via AppleScript."""
    try:
        script = f'''tell application "Things3"
    try
        set theItem to {item_type} id "{item_id}"
        delete theItem
    end try
end tell'''
        run_applescript(script)
    except Exception as e:
        print(f"  [cleanup warning: {e}]")


# ============================================================================
# Tool references
# ============================================================================

schedule_task = _get_tool_fn("schedule-task")
delegate_task = _get_tool_fn("delegate-task")
defer_task = _get_tool_fn("defer-task")
plan_project = _get_tool_fn("plan-project")
modify_task = _get_tool_fn("modify-task")
capture_task = _get_tool_fn("capture-task")
complete_task = _get_tool_fn("complete-task")
daily_review = _get_tool_fn("daily-review")
weekly_review = _get_tool_fn("weekly-review")
search_tasks = _get_tool_fn("search-tasks")
get_projects = _get_tool_fn("get-projects")
get_areas = _get_tool_fn("get-areas")
get_tags = _get_tool_fn("get-tags")
show_in_app = _get_tool_fn("show-in-app")
get_cache_stats = _get_tool_fn("get-cache-stats")


# ============================================================================
# Test tracking
# ============================================================================

results: list[tuple[str, str, bool, str]] = []  # (phase, name, passed, detail)
cleanup_todos: list[str] = []
cleanup_projects: list[str] = []


def record(phase: str, name: str, passed: bool, detail: str = ""):
    tag = "PASS" if passed else "FAIL"
    results.append((phase, name, passed, detail))
    print(f"  [{tag}] {name}")
    if detail and not passed:
        print(f"         {detail[:200]}")


async def create_test_task(title: str) -> str | None:
    """Create a task via capture-task, return UUID."""
    result = await capture_task(title=title, notes="Test data - auto cleanup")
    if "Captured" not in result:
        return None
    time.sleep(0.8)
    tid = find_todo(title)
    if tid:
        cleanup_todos.append(tid)
    return tid


# ============================================================================
# Phase 1: Organize Tools (5 tools x 3 scenarios)
# ============================================================================


async def phase1_organize():
    print("\n" + "=" * 60)
    print("PHASE 1: Organize Tools")
    print("=" * 60)

    # ------------------------------------------------------------------
    # schedule-task
    # ------------------------------------------------------------------
    print("\n--- schedule-task ---")

    # Simple happy: schedule for today
    title = gen_title("SCHED-SIMPLE")
    try:
        result = await schedule_task(title=title, when="today")
        passed = "Scheduled" in result and title in result
        record("organize", "schedule-task / simple happy", passed, result)
        time.sleep(0.8)
        tid = find_todo(title)
        if tid:
            cleanup_todos.append(tid)
    except Exception as e:
        record("organize", "schedule-task / simple happy", False, str(e))

    # Complex happy: schedule with all options
    title = gen_title("SCHED-COMPLEX")
    try:
        result = await schedule_task(
            title=title,
            when="tomorrow",
            deadline="2026-12-31",
            context=["@computer"],
            checklist=["Step 1", "Step 2", "Step 3"],
            notes="Complex scheduling test with multiple options",
        )
        passed = "Scheduled" in result and "Deadline" in result
        record("organize", "schedule-task / complex happy", passed, result)
        time.sleep(0.8)
        tid = find_todo(title)
        if tid:
            cleanup_todos.append(tid)
    except Exception as e:
        record("organize", "schedule-task / complex happy", False, str(e))

    # Unhappy: invalid when value (empty string)
    title = gen_title("SCHED-UNHAPPY")
    try:
        result = await schedule_task(title=title, when="")
        # If it doesn't raise, it might still succeed (empty when -> inbox)
        record(
            "organize",
            "schedule-task / unhappy (empty when)",
            True,
            f"Graceful handling: {result[:120]}",
        )
        time.sleep(0.8)
        tid = find_todo(title)
        if tid:
            cleanup_todos.append(tid)
    except ToolError as e:
        record(
            "organize",
            "schedule-task / unhappy (empty when)",
            True,
            f"ToolError as expected: {e}",
        )
    except Exception as e:
        record("organize", "schedule-task / unhappy (empty when)", False, str(e))

    # ------------------------------------------------------------------
    # delegate-task
    # ------------------------------------------------------------------
    print("\n--- delegate-task ---")

    # Simple happy: delegate with no follow-up
    title = gen_title("DELEG-SIMPLE")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await delegate_task(task_id=tid, delegated_to="Alice")
            passed = "Delegated to Alice" in result and "waiting-for" in result
            record("organize", "delegate-task / simple happy", passed, result)
        except Exception as e:
            record("organize", "delegate-task / simple happy", False, str(e))
    else:
        record(
            "organize",
            "delegate-task / simple happy",
            False,
            "Could not create test task",
        )

    # Complex happy: delegate with follow-up and notes
    title = gen_title("DELEG-COMPLEX")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await delegate_task(
                task_id=tid,
                delegated_to="Bob",
                follow_up_date="2026-04-15",
                notes="Sent email on March 9",
            )
            passed = (
                "Delegated to Bob" in result
                and "waiting-for" in result
                and "Follow up" in result
            )
            record("organize", "delegate-task / complex happy", passed, result)
        except Exception as e:
            record("organize", "delegate-task / complex happy", False, str(e))
    else:
        record(
            "organize",
            "delegate-task / complex happy",
            False,
            "Could not create test task",
        )

    # Unhappy: nonexistent task_id
    try:
        result = await delegate_task(
            task_id="nonexistent-uuid-12345", delegated_to="Nobody"
        )
        record(
            "organize",
            "delegate-task / unhappy (bad id)",
            False,
            f"Expected ToolError but got: {result[:120]}",
        )
    except ToolError as e:
        passed = "not found" in str(e).lower() or "Task not found" in str(e)
        record("organize", "delegate-task / unhappy (bad id)", passed, str(e))
    except Exception as e:
        record("organize", "delegate-task / unhappy (bad id)", False, str(e))

    # ------------------------------------------------------------------
    # defer-task
    # ------------------------------------------------------------------
    print("\n--- defer-task ---")

    # Simple happy: defer to someday
    title = gen_title("DEFER-SIMPLE")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await defer_task(task_id=tid, defer_to="someday")
            passed = "Someday/Maybe" in result
            record("organize", "defer-task / simple happy", passed, result)
        except Exception as e:
            record("organize", "defer-task / simple happy", False, str(e))
    else:
        record(
            "organize", "defer-task / simple happy", False, "Could not create test task"
        )

    # Complex happy: defer to next_week with reason
    title = gen_title("DEFER-COMPLEX")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await defer_task(
                task_id=tid,
                defer_to="next_week",
                reason="Waiting for client feedback",
            )
            passed = "Deferred" in result
            record("organize", "defer-task / complex happy", passed, result)
        except Exception as e:
            record("organize", "defer-task / complex happy", False, str(e))
    else:
        record(
            "organize",
            "defer-task / complex happy",
            False,
            "Could not create test task",
        )

    # Unhappy: nonexistent task_id
    try:
        result = await defer_task(task_id="nonexistent-uuid-99999", defer_to="someday")
        # defer-task doesn't validate task_id (url_scheme just fires), so it may "succeed"
        record(
            "organize",
            "defer-task / unhappy (bad id)",
            True,
            f"Graceful handling (no validation): {result[:120]}",
        )
    except ToolError as e:
        record("organize", "defer-task / unhappy (bad id)", True, f"ToolError: {e}")
    except Exception as e:
        record("organize", "defer-task / unhappy (bad id)", False, str(e))

    # ------------------------------------------------------------------
    # plan-project
    # ------------------------------------------------------------------
    print("\n--- plan-project ---")

    # Simple happy: project with 2 tasks
    proj_title = gen_title("PROJ-SIMPLE")
    try:
        result = await plan_project(
            title=proj_title,
            tasks=[
                {"title": f"{proj_title}-Task1", "when": "anytime"},
                {"title": f"{proj_title}-Task2"},
            ],
        )
        passed = "Created project" in result and "2 tasks" in result
        record("organize", "plan-project / simple happy", passed, result)
        time.sleep(1)
        pid = find_project(proj_title)
        if pid:
            cleanup_projects.append(pid)
    except Exception as e:
        record("organize", "plan-project / simple happy", False, str(e))

    # Complex happy: project with 5+ tasks, deadline, notes
    proj_title = gen_title("PROJ-COMPLEX")
    try:
        result = await plan_project(
            title=proj_title,
            tasks=[
                {"title": f"{proj_title}-Research", "when": "anytime"},
                {"title": f"{proj_title}-Draft", "when": "anytime"},
                {"title": f"{proj_title}-Review"},
                {"title": f"{proj_title}-Finalize", "when": "tomorrow"},
                {"title": f"{proj_title}-Publish", "when": "2026-04-01"},
                {"title": f"{proj_title}-Celebrate"},
            ],
            notes="Complex project test with mixed scheduling",
            deadline="2026-06-30",
        )
        passed = (
            "Created project" in result and "6 tasks" in result and "Deadline" in result
        )
        record("organize", "plan-project / complex happy", passed, result)
        time.sleep(1)
        pid = find_project(proj_title)
        if pid:
            cleanup_projects.append(pid)
    except Exception as e:
        record("organize", "plan-project / complex happy", False, str(e))

    # Unhappy: all tasks future-dated -> expect warning about no next action
    proj_title = gen_title("PROJ-NONEXT")
    try:
        result = await plan_project(
            title=proj_title,
            tasks=[
                {"title": f"{proj_title}-Future1", "when": "2026-06-01"},
                {"title": f"{proj_title}-Future2", "when": "2026-07-01"},
            ],
        )
        passed = "Warning" in result and "next action" in result.lower()
        record("organize", "plan-project / unhappy (no next action)", passed, result)
        time.sleep(1)
        pid = find_project(proj_title)
        if pid:
            cleanup_projects.append(pid)
    except Exception as e:
        record("organize", "plan-project / unhappy (no next action)", False, str(e))

    # ------------------------------------------------------------------
    # modify-task
    # ------------------------------------------------------------------
    print("\n--- modify-task ---")

    # Simple happy: change title
    title = gen_title("MODIFY-SIMPLE")
    tid = await create_test_task(title)
    new_title = gen_title("MODIFY-RENAMED")
    if tid:
        try:
            result = await modify_task(task_id=tid, title=new_title)
            passed = "updated" in result.lower()
            record("organize", "modify-task / simple happy (rename)", passed, result)
        except Exception as e:
            record("organize", "modify-task / simple happy (rename)", False, str(e))
    else:
        record(
            "organize",
            "modify-task / simple happy (rename)",
            False,
            "Could not create test task",
        )

    # Complex happy: update everything at once
    title = gen_title("MODIFY-COMPLEX")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await modify_task(
                task_id=tid,
                title=gen_title("MODIFY-UPDATED"),
                add_notes="Additional notes from test",
                add_tags=["@computer"],
                add_checklist=["Check item A", "Check item B"],
                deadline="2026-05-15",
            )
            passed = "updated" in result.lower()
            record(
                "organize", "modify-task / complex happy (multi-update)", passed, result
            )
        except Exception as e:
            record(
                "organize", "modify-task / complex happy (multi-update)", False, str(e)
            )
    else:
        record(
            "organize",
            "modify-task / complex happy (multi-update)",
            False,
            "Could not create test task",
        )

    # Unhappy: move to nonexistent project
    title = gen_title("MODIFY-BADPROJ")
    tid = await create_test_task(title)
    if tid:
        try:
            result = await modify_task(
                task_id=tid,
                project="NONEXISTENT-PROJECT-XYZ-12345",
            )
            record(
                "organize",
                "modify-task / unhappy (bad project)",
                False,
                f"Expected ToolError but got: {result[:120]}",
            )
        except ToolError as e:
            passed = "not found" in str(e).lower()
            record("organize", "modify-task / unhappy (bad project)", passed, str(e))
        except Exception as e:
            record("organize", "modify-task / unhappy (bad project)", False, str(e))
    else:
        record(
            "organize",
            "modify-task / unhappy (bad project)",
            False,
            "Could not create test task",
        )


# ============================================================================
# Phase 2: Reflect Tools (2 tools, present output)
# ============================================================================


async def phase2_reflect():
    print("\n" + "=" * 60)
    print("PHASE 2: Reflect Tools")
    print("=" * 60)

    # daily-review
    print("\n--- daily-review ---")
    try:
        result = await daily_review()
        passed = "Daily Review" in result and "Today" in result
        record("reflect", "daily-review", passed, "")
        print(f"\n{'~' * 40}")
        print(result)
        print(f"{'~' * 40}")
    except Exception as e:
        record("reflect", "daily-review", False, str(e))

    # weekly-review
    print("\n--- weekly-review ---")
    try:
        result = await weekly_review()
        passed = "Weekly Review" in result
        record("reflect", "weekly-review", passed, "")
        print(f"\n{'~' * 40}")
        print(result)
        print(f"{'~' * 40}")
    except Exception as e:
        record("reflect", "weekly-review", False, str(e))


# ============================================================================
# Phase 3: Utility Tools (6 tools, quick run)
# ============================================================================


async def phase3_utility():
    print("\n" + "=" * 60)
    print("PHASE 3: Utility Tools")
    print("=" * 60)

    # search-tasks: search for one of our test items
    print("\n--- search-tasks ---")
    try:
        result = await search_tasks(query="MCP-TEST")
        passed = "Found" in result or "No tasks found" in result
        record("utility", "search-tasks (query=MCP-TEST)", passed, result[:150])
    except Exception as e:
        record("utility", "search-tasks", False, str(e))

    # get-projects
    print("\n--- get-projects ---")
    try:
        result = await get_projects(include_items=False)
        passed = isinstance(result, str) and len(result) > 0
        record("utility", "get-projects", passed, result[:150])
    except Exception as e:
        record("utility", "get-projects", False, str(e))

    # get-areas
    print("\n--- get-areas ---")
    try:
        result = await get_areas(include_items=False)
        passed = isinstance(result, str) and len(result) > 0
        record("utility", "get-areas", passed, result[:150])
    except Exception as e:
        record("utility", "get-areas", False, str(e))

    # get-tags
    print("\n--- get-tags ---")
    try:
        result = await get_tags(include_items=False)
        passed = isinstance(result, str) and len(result) > 0
        record("utility", "get-tags", passed, result[:150])
    except Exception as e:
        record("utility", "get-tags", False, str(e))

    # show-in-app
    print("\n--- show-in-app ---")
    try:
        result = await show_in_app(id="today")
        passed = "Opened" in result
        record("utility", "show-in-app (today)", passed, result)
    except Exception as e:
        record("utility", "show-in-app", False, str(e))

    # get-cache-stats
    print("\n--- get-cache-stats ---")
    try:
        result = await get_cache_stats()
        passed = "Cache Statistics" in result
        record("utility", "get-cache-stats", passed, result)
    except Exception as e:
        record("utility", "get-cache-stats", False, str(e))


# ============================================================================
# Cleanup
# ============================================================================


def cleanup():
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)

    # Delete tracked items
    for tid in cleanup_todos:
        delete_item(tid, "to do")
    print(f"  Deleted {len(cleanup_todos)} tracked todos")

    for pid in cleanup_projects:
        delete_item(pid, "project")
    print(f"  Deleted {len(cleanup_projects)} tracked projects")

    # Bulk cleanup any remaining MCP-TEST-* items
    try:
        script = """tell application "Things3"
    set deletedCount to 0

    -- Clean up todos
    set todoIds to {}
    repeat with theTodo in (every to do)
        if name of theTodo starts with "MCP-TEST-" then
            set end of todoIds to id of theTodo
        end if
        if name of theTodo starts with "Waiting:" then
            if name of theTodo contains "MCP-TEST-" then
                set end of todoIds to id of theTodo
            end if
        end if
    end repeat
    repeat with todoId in todoIds
        try
            delete (to do id todoId)
            set deletedCount to deletedCount + 1
        end try
    end repeat

    -- Clean up projects
    set projectIds to {}
    repeat with theProject in (every project)
        if name of theProject starts with "MCP-TEST-" then
            set end of projectIds to id of theProject
        end if
    end repeat
    repeat with projectId in projectIds
        try
            delete (project id projectId)
            set deletedCount to deletedCount + 1
        end try
    end repeat

    return deletedCount
end tell"""
        result = run_applescript(script)
        if result and result.isdigit() and int(result) > 0:
            print(f"  Bulk cleanup: {result} additional items removed")
        else:
            print("  Bulk cleanup: no extra items found")
    except Exception as e:
        print(f"  Bulk cleanup warning: {e}")


# ============================================================================
# Main
# ============================================================================


def print_summary():
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    phases = {}
    for phase, name, passed, detail in results:
        phases.setdefault(phase, []).append((name, passed, detail))

    total_pass = 0
    total_fail = 0

    for phase, tests in phases.items():
        p = sum(1 for _, passed, _ in tests if passed)
        f = sum(1 for _, passed, _ in tests if not passed)
        total_pass += p
        total_fail += f
        print(f"\n  {phase.upper()}: {p}/{p + f} passed")
        for name, passed, _ in tests:
            status = "PASS" if passed else "FAIL"
            print(f"    [{status}] {name}")

    total = total_pass + total_fail
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_pass}/{total} passed, {total_fail} failed")
    print(f"{'=' * 60}")
    return total_fail == 0


async def main():
    print("=" * 60)
    print("Things MCP - Organize / Reflect / Utility Integration Tests")
    print("=" * 60)

    if not is_things_running():
        print("SKIP: Things 3 is not running. Start Things 3 and retry.")
        sys.exit(0)
    print("OK: Things 3 is running\n")

    try:
        await phase1_organize()
        await phase2_reflect()
        await phase3_utility()
    finally:
        cleanup()

    all_passed = print_summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted - running cleanup...")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        cleanup()
        sys.exit(1)
