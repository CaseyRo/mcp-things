"""Tests for formatters module - output formatting for todos, projects, areas, tags."""

import pytest
from unittest.mock import patch


pytestmark = [pytest.mark.unit]


class TestFormatTodo:
    """Tests for render_todo()."""

    def test_minimal_todo(self):
        """Format a todo with only required fields."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Buy milk", "uuid": "abc-123", "type": "to-do"}
        result = render_todo(todo)

        assert "Title: Buy milk" in result
        assert "UUID: abc-123" in result
        assert "Type: to-do" in result

    def test_todo_with_status(self):
        """Status field is included when present."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "status": "completed",
        }
        result = render_todo(todo)
        assert "Status: completed" in result

    def test_todo_without_status(self):
        """Status line is omitted when status is empty/None."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Task", "uuid": "u1", "type": "to-do", "status": ""}
        result = render_todo(todo)
        assert "Status:" not in result

    def test_todo_with_dates(self):
        """Start date, deadline, and completion date are formatted."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "start_date": "2026-03-01",
            "deadline": "2026-03-15",
            "stop_date": "2026-03-10",
        }
        result = render_todo(todo)

        assert "Start Date: 2026-03-01" in result
        assert "Deadline: 2026-03-15" in result
        assert "Completed: 2026-03-10" in result

    def test_todo_without_dates(self):
        """Date lines are omitted when not present."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Task", "uuid": "u1", "type": "to-do"}
        result = render_todo(todo)

        assert "Start Date:" not in result
        assert "Deadline:" not in result
        assert "Completed:" not in result

    def test_todo_with_notes(self):
        """Notes are included when present."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "notes": "Some important notes",
        }
        result = render_todo(todo)
        assert "Notes: Some important notes" in result

    def test_todo_with_start_list(self):
        """Start/list location is included."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "start": "today",
        }
        result = render_todo(todo)
        assert "List: today" in result

    def test_todo_with_tags(self):
        """Tags are comma-separated."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "tags": ["urgent", "work", "meeting"],
        }
        result = render_todo(todo)
        assert "Tags: urgent, work, meeting" in result

    def test_todo_with_empty_tags(self):
        """Empty tag list doesn't produce Tags line."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Task", "uuid": "u1", "type": "to-do", "tags": []}
        result = render_todo(todo)
        assert "Tags:" not in result

    def test_todo_with_checklist(self):
        """Checklist items are rendered with status symbols."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "checklist": [
                {"title": "Step 1", "status": "completed"},
                {"title": "Step 2", "status": "open"},
            ],
        }
        result = render_todo(todo)

        assert "Checklist:" in result
        assert "\u2713 Step 1" in result
        assert "\u25a1 Step 2" in result

    def test_todo_with_empty_checklist(self):
        """Empty checklist list still produces header but no items."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Task", "uuid": "u1", "type": "to-do", "checklist": []}
        result = render_todo(todo)
        # Code adds "Checklist:" header for any list (even empty)
        assert "Checklist:" in result
        # But no items follow
        lines = result.split("\n")
        checklist_idx = next(i for i, line in enumerate(lines) if "Checklist:" in line)
        # No more lines after the header (or none with checkbox symbols)
        remaining = lines[checklist_idx + 1 :]
        assert all("\u2713" not in line and "\u25a1" not in line for line in remaining)

    def test_todo_with_no_checklist_key(self):
        """Missing checklist key doesn't produce Checklist line."""
        from things_mcp.formatters import render_todo

        todo = {"title": "Task", "uuid": "u1", "type": "to-do"}
        result = render_todo(todo)
        assert "Checklist:" not in result

    def test_todo_with_project_lookup(self):
        """Project name is resolved via things.get()."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "project": "proj-uuid-123",
        }
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.get.return_value = {"title": "My Project"}
            result = render_todo(todo)

        assert "Project: My Project" in result
        mock_things.get.assert_called_once_with("proj-uuid-123")

    def test_todo_project_lookup_failure(self):
        """Project lookup failure is silently handled."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "project": "bad-uuid",
        }
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.get.side_effect = Exception("DB error")
            result = render_todo(todo)

        assert "Project:" not in result

    def test_todo_with_area_lookup(self):
        """Area name is resolved via things.get()."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "area": "area-uuid-456",
        }
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.get.return_value = {"title": "Personal"}
            result = render_todo(todo)

        assert "Area: Personal" in result

    def test_todo_area_lookup_returns_none(self):
        """Area lookup returning None is handled gracefully."""
        from things_mcp.formatters import render_todo

        todo = {
            "title": "Task",
            "uuid": "u1",
            "type": "to-do",
            "area": "missing-uuid",
        }
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.get.return_value = None
            result = render_todo(todo)

        assert "Area:" not in result


class TestFormatProject:
    """Tests for render_project()."""

    def test_minimal_project(self):
        """Format a project with only required fields."""
        from things_mcp.formatters import render_project

        project = {"title": "Website Redesign", "uuid": "proj-1"}
        with patch("things_mcp.formatters.things"):
            result = render_project(project)

        assert "Title: Website Redesign" in result
        assert "UUID: proj-1" in result

    def test_project_with_notes(self):
        """Project notes are included."""
        from things_mcp.formatters import render_project

        project = {"title": "Proj", "uuid": "p1", "notes": "Important project"}
        with patch("things_mcp.formatters.things"):
            result = render_project(project)

        assert "Notes: Important project" in result

    def test_project_with_area(self):
        """Area is resolved for projects."""
        from things_mcp.formatters import render_project

        project = {"title": "Proj", "uuid": "p1", "area": "area-1"}
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.get.return_value = {"title": "Work"}
            result = render_project(project)

        assert "Area: Work" in result

    def test_project_include_items(self):
        """include_items=True lists todo titles."""
        from things_mcp.formatters import render_project

        project = {"title": "Proj", "uuid": "p1"}
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.todos.return_value = [
                {"title": "Task A"},
                {"title": "Task B"},
            ]
            result = render_project(project, include_items=True)

        assert "Tasks:" in result
        assert "- Task A" in result
        assert "- Task B" in result

    def test_project_include_items_empty(self):
        """No Tasks section when project has no todos."""
        from things_mcp.formatters import render_project

        project = {"title": "Proj", "uuid": "p1"}
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.todos.return_value = []
            result = render_project(project, include_items=True)

        assert "Tasks:" not in result


class TestFormatArea:
    """Tests for render_area()."""

    def test_minimal_area(self):
        """Format an area with only required fields."""
        from things_mcp.formatters import render_area

        area = {"title": "Personal", "uuid": "area-1"}
        with patch("things_mcp.formatters.things"):
            result = render_area(area)

        assert "Title: Personal" in result
        assert "UUID: area-1" in result

    def test_area_with_notes(self):
        from things_mcp.formatters import render_area

        area = {"title": "Work", "uuid": "a1", "notes": "All work stuff"}
        with patch("things_mcp.formatters.things"):
            result = render_area(area)

        assert "Notes: All work stuff" in result

    def test_area_include_items(self):
        """include_items lists both projects and todos."""
        from things_mcp.formatters import render_area

        area = {"title": "Work", "uuid": "a1"}
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.projects.return_value = [{"title": "Project X"}]
            mock_things.todos.return_value = [{"title": "Loose task"}]
            result = render_area(area, include_items=True)

        assert "Projects:" in result
        assert "- Project X" in result
        assert "Tasks:" in result
        assert "- Loose task" in result


class TestFormatTag:
    """Tests for render_tag()."""

    def test_minimal_tag(self):
        from things_mcp.formatters import render_tag

        tag = {"title": "urgent", "uuid": "tag-1"}
        with patch("things_mcp.formatters.things"):
            result = render_tag(tag)

        assert "Title: urgent" in result
        assert "UUID: tag-1" in result

    def test_tag_with_shortcut(self):
        from things_mcp.formatters import render_tag

        tag = {"title": "urgent", "uuid": "tag-1", "shortcut": "u"}
        with patch("things_mcp.formatters.things"):
            result = render_tag(tag)

        assert "Shortcut: u" in result

    def test_tag_include_items(self):
        from things_mcp.formatters import render_tag

        tag = {"title": "urgent", "uuid": "tag-1"}
        with patch("things_mcp.formatters.things") as mock_things:
            mock_things.todos.return_value = [{"title": "Fix bug"}]
            result = render_tag(tag, include_items=True)

        assert "Tagged Items:" in result
        assert "- Fix bug" in result
