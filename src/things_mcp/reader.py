"""Unified read interface — SQLite reader with things-py fallback.

This module provides a drop-in API matching the things-py calling conventions
so tools can switch from `import things; things.inbox()` to
`from .reader import reader; reader.inbox()` with no other changes.

The SQLite reader is preferred for performance; things-py is the fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_reader = None


def _get_sqlite_reader():
    """Lazy-init the SQLite reader singleton."""
    global _reader
    if _reader is None:
        try:
            from .sqlite_reader import get_reader

            _reader = get_reader()
            logger.info("SQLite reader initialized — direct database reads enabled")
        except Exception:
            logger.warning("SQLite reader unavailable — using things-py for reads")
            _reader = False  # sentinel: tried and failed
    return _reader if _reader is not False else None


def inbox() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_inbox()
    import things

    return things.inbox()


def today() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_today()
    import things

    return things.today()


def upcoming() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_upcoming()
    import things

    return things.upcoming()


def anytime() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_anytime()
    import things

    return things.anytime()


def someday() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_someday()
    import things

    return things.someday()


def todos(**kwargs) -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_todos(**kwargs)
    import things

    return things.todos(**kwargs)


def projects(**kwargs) -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_projects(**kwargs)
    import things

    return things.projects(**kwargs)


def areas() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_areas()
    import things

    return things.areas()


def tags() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.get_tags()
    import things

    return things.tags()


def search(query: str) -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        return r.search(query)
    import things

    return things.search(query)


# Pass-through for write-adjacent reads that need things-py directly
def get(uuid: str) -> Optional[dict[str, Any]]:
    """Get a single item by UUID — always uses things-py (not worth caching)."""
    import things

    return things.get(uuid)


def last(period: str, **kwargs) -> list[dict[str, Any]]:
    """Get recently modified items — uses things-py."""
    import things

    return things.last(period, **kwargs)


def checklist_items(task_uuid: str) -> list[dict[str, Any]]:
    """Get checklist items for a task — uses things-py."""
    import things

    return things.checklist_items(task_uuid)


def trash() -> list[dict[str, Any]]:
    """Get trashed items — uses things-py."""
    import things

    return things.trash()


def logbook() -> list[dict[str, Any]]:
    """Get logbook items — uses things-py."""
    import things

    if hasattr(things, "logbook"):
        return things.logbook()
    return things.last("7d", status="completed")
