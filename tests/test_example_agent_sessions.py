"""The decision logic of examples/agent-sessions/things_sessions.py (no Things needed)."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parent.parent
    / "examples"
    / "agent-sessions"
    / "things_sessions.py"
)
_spec = importlib.util.spec_from_file_location("things_sessions", _PATH)
ts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ts)

TODAY = date(2026, 10, 29)


@pytest.fixture
def repos(tmp_path):
    (tmp_path / "mcp-things").mkdir()
    (tmp_path / "blog").mkdir()
    return tmp_path


def todo(tags, when=None):
    return {"id": "x", "name": "Task", "tags": tags, "when": when}


@pytest.mark.unit
def test_starts_in_the_tagged_repo(repos):
    assert ts.ready(todo("claude, mcp-things"), TODAY, repos) == repos / "mcp-things"


@pytest.mark.unit
def test_needs_a_repo_tag(repos):
    assert ts.ready(todo("claude, errands"), TODAY, repos) is None


@pytest.mark.unit
def test_runs_once(repos):
    assert ts.ready(todo("claude, mcp-things, started"), TODAY, repos) is None


@pytest.mark.unit
def test_waits_for_the_when_date(repos):
    assert ts.ready(todo("claude, blog", when="2026-10-30"), TODAY, repos) is None
    assert (
        ts.ready(todo("claude, blog", when="2026-10-29"), TODAY, repos)
        == repos / "blog"
    )


@pytest.mark.unit
def test_repo_pick_is_stable_and_ignores_control_tags(repos):
    (repos / "go").mkdir()
    assert (
        ts.ready(todo("Claude, mcp-things, go, blog"), TODAY, repos) == repos / "blog"
    )
