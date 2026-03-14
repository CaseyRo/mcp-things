"""Tests for fast_server module utilities."""

from unittest import mock

import pytest


class TestBuildDashboardData:
    """Test _build_dashboard_data helper."""

    def test_returns_expected_keys(self):
        from things_mcp.fast_server import _build_dashboard_data

        tracker = mock.Mock()
        tracker.get_summary.return_value = {"total": 5, "actions": {}}
        tracker.get_trends.return_value = []

        data = _build_dashboard_data(tracker, 30)
        assert data["days"] == 30
        assert "summary" in data
        assert "trends" in data

    def test_zero_days_uses_all_time(self):
        from things_mcp.fast_server import _build_dashboard_data

        tracker = mock.Mock()
        tracker.get_summary.return_value = {"total": 0, "actions": {}}
        tracker.get_trends.return_value = []

        data = _build_dashboard_data(tracker, 0)
        assert data["days"] == 0
        tracker.get_trends.assert_called_once_with(weeks=12)

    def test_seven_days_uses_four_weeks(self):
        from things_mcp.fast_server import _build_dashboard_data

        tracker = mock.Mock()
        tracker.get_summary.return_value = {"total": 0, "actions": {}}
        tracker.get_trends.return_value = []

        _build_dashboard_data(tracker, 7)
        tracker.get_trends.assert_called_once_with(weeks=4)


class TestTrailingSlashMiddleware:
    """Test _TrailingSlashMiddleware."""

    @pytest.mark.asyncio
    async def test_rewrites_mcp_path(self):
        from things_mcp.fast_server import _TrailingSlashMiddleware

        calls = []

        async def mock_app(scope, receive, send):
            calls.append(scope["path"])

        middleware = _TrailingSlashMiddleware(mock_app)
        scope = {"type": "http", "path": "/mcp"}
        await middleware(scope, None, None)
        assert calls[0] == "/mcp/"

    @pytest.mark.asyncio
    async def test_leaves_other_paths_alone(self):
        from things_mcp.fast_server import _TrailingSlashMiddleware

        calls = []

        async def mock_app(scope, receive, send):
            calls.append(scope["path"])

        middleware = _TrailingSlashMiddleware(mock_app)
        scope = {"type": "http", "path": "/dashboard"}
        await middleware(scope, None, None)
        assert calls[0] == "/dashboard"

    def test_delegates_attributes(self):
        from things_mcp.fast_server import _TrailingSlashMiddleware

        app = mock.Mock()
        app.routes = ["route1"]
        middleware = _TrailingSlashMiddleware(app)
        assert middleware.routes == ["route1"]


class TestServerStats:
    """Test ServerStats from server_core."""

    def test_record_and_summary(self):
        from things_mcp.server_core import ServerStats

        stats = ServerStats()
        stats.record_tool_call("get-tasks", success=True)
        stats.record_tool_call("get-tasks", success=True)
        stats.record_tool_call("capture-task", success=True)
        stats.record_tool_call("capture-task", success=False)

        summary = stats.get_summary()
        assert summary["total_calls"] == 4
        assert summary["unique_tools"] == 2
        assert summary["errors"] == 1
        assert summary["top_tools"][0][0] == "get-tasks"
        assert summary["top_tools"][0][1] == 2

    def test_uptime_seconds(self):
        from things_mcp.server_core import ServerStats
        import time

        stats = ServerStats()
        stats.start_time = time.time() - 30
        assert "s" in stats.get_uptime()

    def test_uptime_minutes(self):
        from things_mcp.server_core import ServerStats
        import time

        stats = ServerStats()
        stats.start_time = time.time() - 120
        assert "m" in stats.get_uptime()

    def test_uptime_hours(self):
        from things_mcp.server_core import ServerStats
        import time

        stats = ServerStats()
        stats.start_time = time.time() - 7200
        assert "h" in stats.get_uptime()
