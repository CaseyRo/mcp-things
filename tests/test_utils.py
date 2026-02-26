"""Tests for utils module - CircuitBreaker, RateLimiter, DeadLetterQueue."""

import time
import pytest
import mcp.types as types


pytestmark = [pytest.mark.unit]


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    def _make_cb(self, failure_threshold=3, recovery_timeout=1):
        from things_mcp.utils import CircuitBreaker

        return CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def test_starts_closed(self):
        cb = self._make_cb()
        assert cb.state == "closed"
        assert cb.allow_operation() is True

    def test_stays_closed_below_threshold(self):
        """Failures below threshold keep circuit closed."""
        cb = self._make_cb(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == "closed"
        assert cb.allow_operation() is True

    def test_opens_at_threshold(self):
        """Circuit opens when failure threshold is reached."""
        cb = self._make_cb(failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.state == "open"
        assert cb.allow_operation() is False

    def test_open_blocks_operations(self):
        """Open circuit blocks all operations."""
        cb = self._make_cb(failure_threshold=1)
        cb.record_failure()

        assert cb.allow_operation() is False

    def test_transitions_to_half_open_after_timeout(self):
        """After recovery timeout, circuit transitions to half-open."""
        cb = self._make_cb(failure_threshold=1, recovery_timeout=0)

        cb.record_failure()
        assert cb.state == "open"

        # Recovery timeout is 0 seconds, so it should transition immediately
        time.sleep(0.01)
        assert cb.allow_operation() is True
        assert cb.state == "half-open"

    def test_half_open_success_closes_circuit(self):
        """Success in half-open state resets circuit to closed."""
        cb = self._make_cb(failure_threshold=1, recovery_timeout=0)

        cb.record_failure()
        time.sleep(0.01)
        cb.allow_operation()  # transitions to half-open
        cb.record_success()

        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_success_resets_failure_count_when_closed(self):
        """Success in closed state resets failure count."""
        cb = self._make_cb(failure_threshold=5)

        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_half_open_allows_single_test(self):
        """Half-open state allows operations (for testing recovery)."""
        cb = self._make_cb(failure_threshold=1, recovery_timeout=0)

        cb.record_failure()
        time.sleep(0.01)

        # First call transitions to half-open and allows
        assert cb.allow_operation() is True
        assert cb.state == "half-open"

        # Half-open allows subsequent operations too
        assert cb.allow_operation() is True


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_first_operation_immediate(self):
        """First operation doesn't wait."""
        from things_mcp.utils import RateLimiter

        rl = RateLimiter(operations_per_minute=60)
        rl.last_operation_time = 0  # Reset

        start = time.time()
        rl.wait_if_needed()
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 0.1

    def test_rate_limiting_enforced(self):
        """Rapid successive calls are throttled."""
        from things_mcp.utils import RateLimiter

        rl = RateLimiter(operations_per_minute=600)  # 0.1s interval
        rl.last_operation_time = 0

        rl.wait_if_needed()  # First call, immediate
        start = time.time()
        rl.wait_if_needed()  # Should wait ~0.1s
        elapsed = time.time() - start

        # Should have waited at least some time (0.1s interval)
        assert elapsed >= 0.05  # Allow some tolerance

    def test_operation_interval_calculation(self):
        """Operation interval is correctly calculated from ops/minute."""
        from things_mcp.utils import RateLimiter

        rl = RateLimiter(operations_per_minute=30)
        assert rl.operation_interval == 2.0

        rl2 = RateLimiter(operations_per_minute=60)
        assert rl2.operation_interval == 1.0

    def test_decorator_usage(self):
        """RateLimiter can be used as a decorator."""
        from things_mcp.utils import RateLimiter

        rl = RateLimiter(operations_per_minute=6000)  # Fast for tests
        call_count = 0

        @rl
        def my_function():
            nonlocal call_count
            call_count += 1
            return "done"

        result = my_function()
        assert result == "done"
        assert call_count == 1


class TestDeadLetterQueue:
    """Tests for DeadLetterQueue."""

    def _make_dlq(self, tmp_path):
        from things_mcp.utils import DeadLetterQueue

        dlq_file = str(tmp_path / "test_dlq.json")
        return DeadLetterQueue(dlq_file=dlq_file)

    def test_starts_empty(self, tmp_path):
        dlq = self._make_dlq(tmp_path)
        assert len(dlq.queue) == 0

    def test_add_failed_operation(self, tmp_path):
        dlq = self._make_dlq(tmp_path)
        dlq.add_failed_operation("add", {"title": "Test"}, "Connection error")

        assert len(dlq.queue) == 1
        entry = dlq.queue[0]
        assert entry["operation"] == "add"
        assert entry["params"] == {"title": "Test"}
        assert entry["error"] == "Connection error"
        assert entry["attempts"] == 1

    def test_persists_to_disk(self, tmp_path):
        from things_mcp.utils import DeadLetterQueue

        dlq_file = str(tmp_path / "persist_dlq.json")
        dlq1 = DeadLetterQueue(dlq_file=dlq_file)
        dlq1.add_failed_operation("add", {"title": "Test"}, "Error")

        # Load a new instance from the same file
        dlq2 = DeadLetterQueue(dlq_file=dlq_file)
        assert len(dlq2.queue) == 1
        assert dlq2.queue[0]["operation"] == "add"

    def test_retry_all_empty_queue(self, tmp_path):
        dlq = self._make_dlq(tmp_path)
        result = dlq.retry_all()

        assert result["success"] is True
        assert result["retried"] == 0
        assert result["failed"] == 0

    def test_load_queue_missing_file(self, tmp_path):
        """Missing DLQ file starts with empty queue."""
        from things_mcp.utils import DeadLetterQueue

        dlq = DeadLetterQueue(dlq_file=str(tmp_path / "nonexistent.json"))
        assert dlq.queue == []

    def test_load_queue_corrupt_file(self, tmp_path):
        """Corrupt DLQ file falls back to empty queue."""
        from things_mcp.utils import DeadLetterQueue

        dlq_file = tmp_path / "corrupt.json"
        dlq_file.write_text("not valid json{{{")

        dlq = DeadLetterQueue(dlq_file=str(dlq_file))
        assert dlq.queue == []


class TestValidateToolRegistration:
    """Tests for validate_tool_registration()."""

    def _make_tool(self, name, description="A valid description for testing"):
        return types.Tool(
            name=name,
            description=description,
            inputSchema={"type": "object", "properties": {}},
        )

    def test_all_required_tools_present(self):
        """Returns True when all required tools are registered."""
        from things_mcp.utils import validate_tool_registration

        required_names = [
            "get-inbox",
            "get-today",
            "get-upcoming",
            "get-anytime",
            "get-someday",
            "get-logbook",
            "get-trash",
            "get-todos",
            "get-projects",
            "get-areas",
            "get-tags",
            "get-tagged-items",
            "search-todos",
            "search-advanced",
            "get-recent",
            "add-todo",
            "search-items",
            "add-project",
            "update-todo",
            "update-project",
            "show-item",
        ]
        tools = [self._make_tool(name) for name in required_names]

        assert validate_tool_registration(tools) is True

    def test_missing_tool(self):
        """Returns False when required tools are missing."""
        from things_mcp.utils import validate_tool_registration

        tools = [self._make_tool("get-inbox")]  # Missing most tools

        assert validate_tool_registration(tools) is False

    def test_extra_tools_ok(self):
        """Extra tools beyond required ones don't cause failure."""
        from things_mcp.utils import validate_tool_registration

        required_names = [
            "get-inbox",
            "get-today",
            "get-upcoming",
            "get-anytime",
            "get-someday",
            "get-logbook",
            "get-trash",
            "get-todos",
            "get-projects",
            "get-areas",
            "get-tags",
            "get-tagged-items",
            "search-todos",
            "search-advanced",
            "get-recent",
            "add-todo",
            "search-items",
            "add-project",
            "update-todo",
            "update-project",
            "show-item",
        ]
        tools = [self._make_tool(name) for name in required_names]
        tools.append(self._make_tool("bonus-tool"))

        assert validate_tool_registration(tools) is True
