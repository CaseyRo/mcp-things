"""Pytest configuration and shared fixtures for Things MCP tests."""

import pytest
import unittest.mock as mock
from typing import List, Dict, Any, Optional
import time
import uuid
import subprocess
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import settings first - pydantic-settings automatically loads .env
# This ensures THINGS_AUTH_TOKEN is available for all modules
from things_mcp.settings import get_settings

get_settings()  # Trigger settings load

import mcp.types as types  # noqa: E402 - must load after settings


# ============================================================================
# Test helpers
# ============================================================================


def tool_text(result) -> str:
    """Extract the human-readable text body from a tool result.

    Tools migrated to ``ToolResult`` (see openspec change
    ``structured-json-tool-output``) return a ``ToolResult`` whose first
    ``content`` block is the text fallback. Pre-migration tools still return
    plain strings. This helper accepts both so tests can assert on the text
    body uniformly.
    """
    if isinstance(result, str):
        return result
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return text
    return str(result)


# ============================================================================
# Pytest Plugins
# ============================================================================

pytest_plugins = ["tests.pytest_test_results"]

# ============================================================================
# Mock Data Generators
# ============================================================================


def create_mock_todo(
    uuid_str: Optional[str] = None,
    title: str = "Test Todo",
    notes: Optional[str] = None,
    status: str = "open",
    tags: Optional[List[str]] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    project: Optional[str] = None,
    area: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a mock todo dictionary matching things-py format."""
    return {
        "uuid": uuid_str or f"test-todo-{uuid.uuid4().hex[:8]}",
        "type": "to-do",
        "title": title,
        "notes": notes or "",
        "status": status,
        "tags": tags or [],
        "when": when,
        "deadline": deadline,
        "project": project,
        "area": area,
        "start": when or "inbox",
        "start_date": when,
        "stop_date": None,
        "checklist": [],
    }


def create_mock_project(
    uuid_str: Optional[str] = None,
    title: str = "Test Project",
    notes: Optional[str] = None,
    status: str = "open",
    tags: Optional[List[str]] = None,
    when: Optional[str] = None,
    deadline: Optional[str] = None,
    area: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a mock project dictionary matching things-py format."""
    return {
        "uuid": uuid_str or f"test-project-{uuid.uuid4().hex[:8]}",
        "type": "project",
        "title": title,
        "notes": notes or "",
        "status": status,
        "tags": tags or [],
        "when": when,
        "deadline": deadline,
        "area": area,
        "items": items or [],
    }


def create_mock_area(
    uuid_str: Optional[str] = None,
    title: str = "Test Area",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a mock area dictionary matching things-py format."""
    return {
        "uuid": uuid_str or f"test-area-{uuid.uuid4().hex[:8]}",
        "type": "area",
        "title": title,
        "notes": notes or "",
    }


def create_mock_tag(
    uuid_str: Optional[str] = None,
    title: str = "test-tag",
    shortcut: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a mock tag dictionary matching things-py format."""
    return {
        "uuid": uuid_str or f"test-tag-{uuid.uuid4().hex[:8]}",
        "type": "tag",
        "title": title,
        "shortcut": shortcut,
    }


# ============================================================================
# Unit Test Fixtures (Mocked)
# ============================================================================


@pytest.fixture
def mock_things(monkeypatch):
    """Mock the things-py library for unit tests."""
    mock_things_module = mock.MagicMock()

    # Mock common functions
    mock_things_module.inbox = mock.Mock(return_value=[])
    mock_things_module.today = mock.Mock(return_value=[])
    mock_things_module.upcoming = mock.Mock(return_value=[])
    mock_things_module.anytime = mock.Mock(return_value=[])
    mock_things_module.someday = mock.Mock(return_value=[])
    mock_things_module.trash = mock.Mock(return_value=[])
    mock_things_module.last = mock.Mock(return_value=[])
    mock_things_module.todos = mock.Mock(return_value=[])
    mock_things_module.projects = mock.Mock(return_value=[])
    mock_things_module.areas = mock.Mock(return_value=[])
    mock_things_module.tags = mock.Mock(return_value=[])
    mock_things_module.get = mock.Mock(return_value=None)
    mock_things_module.search = mock.Mock(return_value=[])

    # Patch the things module in modules that still import it directly
    monkeypatch.setattr("things_mcp.formatters.things", mock_things_module)
    monkeypatch.setattr("things_mcp.tools_gtd_organize.things", mock_things_module)
    monkeypatch.setattr("things_mcp.resolvers.things", mock_things_module)

    # Patch the reader (db) module in tool modules that use it for reads
    monkeypatch.setattr("things_mcp.tools_gtd_core.db", mock_things_module)
    monkeypatch.setattr("things_mcp.tools_gtd_reflect.db", mock_things_module)
    monkeypatch.setattr("things_mcp.tools_utility.db", mock_things_module)

    return mock_things_module


@pytest.fixture
def mock_applescript(monkeypatch):
    """Mock AppleScript execution for unit tests."""
    mock_run_applescript = mock.Mock(return_value="test-todo-id-123")

    monkeypatch.setattr(
        "things_mcp.applescript_bridge.run_applescript", mock_run_applescript
    )

    return {"run_applescript": mock_run_applescript}


@pytest.fixture
def mock_url_scheme(monkeypatch):
    """Mock URL scheme execution for unit tests."""
    mock_execute_url = mock.Mock(return_value=True)
    mock_execute_xcallback_url = mock.Mock(return_value=True)

    monkeypatch.setattr("things_mcp.url_scheme.execute_url", mock_execute_url)
    monkeypatch.setattr(
        "things_mcp.url_scheme.execute_xcallback_url", mock_execute_xcallback_url
    )

    return {
        "execute_url": mock_execute_url,
        "execute_xcallback_url": mock_execute_xcallback_url,
    }


@pytest.fixture
def mock_utils(monkeypatch):
    """Mock utility functions for unit tests."""
    # Mock app_state (used by fast_server.py for checking Things availability)
    mock_app_state = mock.Mock()
    mock_app_state.update_app_state = mock.Mock(return_value=True)
    mock_app_state.wait_for_app_availability = mock.Mock(return_value=True)

    # Mock circuit_breaker (used by url_scheme.py)
    mock_circuit_breaker = mock.Mock()
    mock_circuit_breaker.allow_operation = mock.Mock(return_value=True)
    mock_circuit_breaker.record_success = mock.Mock()
    mock_circuit_breaker.record_failure = mock.Mock()

    # Mock rate_limiter (used by url_scheme.py)
    mock_rate_limiter = mock.Mock()
    mock_rate_limiter.wait_if_needed = mock.Mock()

    monkeypatch.setattr("things_mcp.fast_server.app_state", mock_app_state)
    monkeypatch.setattr("things_mcp.url_scheme.circuit_breaker", mock_circuit_breaker)
    monkeypatch.setattr("things_mcp.url_scheme.rate_limiter", mock_rate_limiter)

    return {
        "app_state": mock_app_state,
        "circuit_breaker": mock_circuit_breaker,
        "rate_limiter": mock_rate_limiter,
    }


# ============================================================================
# Real Integration Test Fixtures
# ============================================================================


def is_things_available() -> bool:
    """Check if Things 3 is available for real integration tests."""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to (name of processes) contains "Things3"',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except Exception:
        return False


@pytest.fixture(scope="session")
def things_available():
    """Check if Things 3 is available for real integration tests."""
    return is_things_available()


@pytest.fixture(autouse=True)
def skip_real_tests_if_unavailable(request, things_available):
    """Skip real integration tests if Things 3 is not available."""
    if "real" in request.keywords and not things_available:
        pytest.skip("Things 3 is not available for real integration tests")


class TestDataTracker:
    """Track created test items for automatic cleanup."""

    def __init__(self):
        self.created_todos: List[str] = []
        self.created_projects: List[str] = []
        self.created_tags: List[str] = []

    def add_todo(self, todo_id: str):
        """Track a created todo."""
        self.created_todos.append(todo_id)

    def add_project(self, project_id: str):
        """Track a created project."""
        self.created_projects.append(project_id)

    def add_tag(self, tag_name: str):
        """Track a created tag."""
        if tag_name not in self.created_tags:
            self.created_tags.append(tag_name)

    def cleanup(self):
        """Clean up all tracked test items."""
        # Use run_applescript for proper execution (handles multi-line scripts correctly)
        from things_mcp.applescript_bridge import run_applescript

        # Delete todos
        for todo_id in self.created_todos:
            try:
                # Use AppleScript to delete the todo
                # Note: run_applescript handles multi-line scripts via stdin
                script = f"""tell application "Things3"
    try
        set theTodo to to do id "{todo_id}"
        delete theTodo
    end try
end tell"""
                result = run_applescript(script)
                if result is False:
                    # Log but don't fail - cleanup errors are non-critical
                    print(f"Warning: Failed to delete todo {todo_id}")
            except Exception as e:
                # Ignore cleanup errors - they're non-critical
                print(f"Warning: Exception during todo cleanup for {todo_id}: {e}")

        # Delete projects
        for project_id in self.created_projects:
            try:
                script = f"""tell application "Things3"
    try
        set theProject to project id "{project_id}"
        delete theProject
    end try
end tell"""
                result = run_applescript(script)
                if result is False:
                    print(f"Warning: Failed to delete project {project_id}")
            except Exception as e:
                print(
                    f"Warning: Exception during project cleanup for {project_id}: {e}"
                )

        # Clear tracked items
        self.created_todos.clear()
        self.created_projects.clear()
        self.created_tags.clear()

    def cleanup_all_test_items(self):
        """Clean up ALL test items matching test prefixes, not just tracked ones.

        This is useful for cleaning up leftover test data from previous test runs.
        """
        from things_mcp.applescript_bridge import run_applescript

        # Test prefixes to match (documented here, hardcoded in AppleScript below)
        _test_prefixes = [
            "MCP-TEST-TODO",
            "MCP-TAG-TEST",
            "MCP-WORKFLOW-UPDATED",
            "MCP-TEST-TODO-FULL",
            "MCP-TEST-TODO-COMPLETE",
            "MCP-TEST-PROJECT",
        ]
        _ = _test_prefixes  # Silence unused variable warning (used for documentation)

        try:
            # Build AppleScript to find and delete all matching todos and projects
            # Important: Collect IDs first, then delete them (can't delete while iterating)
            script_parts = ['tell application "Things3"']
            script_parts.append(
                '    set testPrefixes to {"MCP-TEST-TODO", "MCP-TAG-TEST", "MCP-WORKFLOW-UPDATED", "MCP-TEST-TODO-FULL", "MCP-TEST-TODO-COMPLETE"}'
            )
            script_parts.append("    set todoIds to {}")
            script_parts.append("    set projectIds to {}")
            script_parts.append("    ")
            script_parts.append(
                "    -- Collect todo IDs (search ALL todos, not just specific lists)"
            )
            script_parts.append("    repeat with theTodo in (every to do)")
            script_parts.append("        set todoName to name of theTodo")
            script_parts.append("        repeat with prefix in testPrefixes")
            script_parts.append("            if todoName starts with prefix then")
            script_parts.append("                set end of todoIds to id of theTodo")
            script_parts.append("                exit repeat")
            script_parts.append("            end if")
            script_parts.append("        end repeat")
            script_parts.append("    end repeat")
            script_parts.append("    ")
            script_parts.append("    -- Collect project IDs")
            script_parts.append("    repeat with theProject in (every project)")
            script_parts.append("        set projectName to name of theProject")
            script_parts.append(
                '        if projectName starts with "MCP-TEST-PROJECT" then'
            )
            script_parts.append("            set end of projectIds to id of theProject")
            script_parts.append("        end if")
            script_parts.append("    end repeat")
            script_parts.append("    ")
            script_parts.append("    -- Delete todos by ID")
            script_parts.append("    set deletedCount to 0")
            script_parts.append("    repeat with todoId in todoIds")
            script_parts.append("        try")
            script_parts.append("            set theTodo to to do id todoId")
            script_parts.append("            delete theTodo")
            script_parts.append("            set deletedCount to deletedCount + 1")
            script_parts.append("        end try")
            script_parts.append("    end repeat")
            script_parts.append("    ")
            script_parts.append("    -- Delete projects by ID")
            script_parts.append("    repeat with projectId in projectIds")
            script_parts.append("        try")
            script_parts.append("            set theProject to project id projectId")
            script_parts.append("            delete theProject")
            script_parts.append("            set deletedCount to deletedCount + 1")
            script_parts.append("        end try")
            script_parts.append("    end repeat")
            script_parts.append("    ")
            script_parts.append("    return deletedCount")
            script_parts.append("end tell")

            script = "\n".join(script_parts)
            result = run_applescript(script)

            if result and result.isdigit():
                count = int(result)
                if count > 0:
                    print(f"Cleaned up {count} test items")
            elif result is False:
                print("Warning: Failed to cleanup all test items")
        except Exception as e:
            print(f"Warning: Exception during bulk cleanup: {e}")


@pytest.fixture
def test_data_tracker():
    """Fixture to track test data for automatic cleanup in real integration tests."""
    tracker = TestDataTracker()
    yield tracker
    # Cleanup tracked items after test
    tracker.cleanup()


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_test_items_on_exit():
    """Session-scoped fixture to cleanup all test items at the end of the test session.

    This ensures any leftover test data from previous runs or failed tests is cleaned up.
    """
    yield
    # Run cleanup at the end of the test session
    tracker = TestDataTracker()
    tracker.cleanup_all_test_items()


def generate_test_title(prefix: str = "MCP-TEST") -> str:
    """Generate a unique test title with timestamp."""
    timestamp = int(time.time())
    random_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{random_suffix}"


# ============================================================================
# MCP Integration Test Fixtures
# ============================================================================


# Note: TestClient doesn't work with streamable-http transport because it requires
# lifespan initialization. We use real server processes for integration tests instead.


@pytest.fixture(scope="session")
def mcp_server_process():
    """Start MCP server in background for real integration tests.

    Only used for tests that require a real HTTP server (marked with @pytest.mark.real).
    Most tests should use mcp_test_client fixture instead.
    """
    import subprocess
    import sys
    import os
    from pathlib import Path

    # Use the entry point script at project root
    server_script = Path(__file__).parent.parent / "things_fast_server.py"

    # Set transport to streamable-http only for testing
    original_transport = os.environ.get("THINGS_MCP_TRANSPORT")
    os.environ["THINGS_MCP_TRANSPORT"] = "streamable-http"

    # Change to project root for proper imports
    project_root = Path(__file__).parent.parent

    try:
        process = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env=os.environ.copy(),
        )
        # Wait for server to start
        time.sleep(3)

        # Verify server is running
        if process.poll() is not None:
            # Server died - check stderr
            stdout, stderr = process.communicate()
            pytest.skip(f"Server failed to start: {stderr}")

        yield process

        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    finally:
        # Restore original transport setting
        if original_transport is not None:
            os.environ["THINGS_MCP_TRANSPORT"] = original_transport
        elif "THINGS_MCP_TRANSPORT" in os.environ:
            del os.environ["THINGS_MCP_TRANSPORT"]


@pytest.fixture
async def mcp_client(mcp_server_process):
    """Create MCP client connected to real server process.

    Only used for tests marked with @pytest.mark.real.
    """
    from tests.mcp_client import create_mcp_client
    import httpx

    # Wait and verify server is accessible
    settings = get_settings()
    base_url = f"http://{settings.things_mcp_host}:{settings.things_mcp_port}"

    # Try to connect with retries
    max_retries = 10
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as test_client:
                # Try POST to /mcp endpoint (GET might return 405)
                response = await test_client.post(
                    f"{base_url}/mcp",
                    json={"jsonrpc": "2.0", "id": "test", "method": "tools/list"},
                    timeout=2,
                )
                # Any response means server is up
                if response.status_code in [200, 400, 404, 405]:
                    break
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            pytest.skip(f"Server not accessible after {max_retries} attempts: {e}")
    else:
        pytest.skip("Server not accessible")

    client = await create_mcp_client(base_url)
    yield client
    await client.close()


# ============================================================================
# Test Utilities
# ============================================================================


def assert_text_content(
    response: List[Any], expected_text_contains: Optional[str] = None
):
    """Assert that response is a list of TextContent with expected content."""
    assert isinstance(response, list)
    assert len(response) > 0
    assert isinstance(response[0], types.TextContent)
    assert response[0].type == "text"

    if expected_text_contains:
        assert expected_text_contains in response[0].text


def assert_error_response(
    response: List[Any], expected_error_contains: Optional[str] = None
):
    """Assert that response indicates an error."""
    assert isinstance(response, list)
    assert len(response) > 0
    assert isinstance(response[0], types.TextContent)

    # Check if it's an error (starts with ⚠️ or contains "Error")
    error_indicators = ["⚠️", "Error", "error"]
    has_error = any(indicator in response[0].text for indicator in error_indicators)
    assert has_error, f"Expected error response but got: {response[0].text}"

    if expected_error_contains:
        assert expected_error_contains in response[0].text
