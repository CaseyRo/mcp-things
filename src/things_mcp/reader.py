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


def _merge_overlay(
    rows: list[dict[str, Any]],
    *,
    query: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Fold just-written (not-yet-persisted) items into a read result.

    See ``write_overlay`` and CDI-1255: Things does not flush URL-scheme writes
    to SQLite immediately, so same-session reads merge the in-process overlay to
    achieve read-your-writes consistency. De-dupes by title against ``rows`` so
    a persisted item is never double-counted.
    """
    try:
        from .write_overlay import get_overlay

        return get_overlay().merge_into(rows, query=query, status=status)
    except Exception:
        logger.debug("reader: overlay merge skipped (non-critical)")
        return rows


def index_stale() -> bool:
    """True if the SQLite snapshot is behind a recent write (CDI-1255).

    Lets read tools distinguish a genuine "not found" from "the index may be
    stale because something was just written". Best-effort; returns False on any
    error so callers default to treating reads as authoritative.
    """
    try:
        from .write_overlay import get_overlay

        return get_overlay().is_index_stale()
    except Exception:
        return False


def inbox() -> list[dict[str, Any]]:
    r = _get_sqlite_reader()
    if r:
        rows = r.get_inbox()
    else:
        import things

        rows = things.inbox()
    return _merge_overlay(rows, status="incomplete")


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
        rows = r.get_todos(**kwargs)
    else:
        import things

        rows = things.todos(**kwargs)
    # Only merge the overlay for broad incomplete queries: a freshly captured
    # item has no project/area/tag/deadline yet, so a filtered query for those
    # should not surface it (it would be a false match).
    status = kwargs.get("status", "incomplete")
    has_narrow_filter = any(
        kwargs.get(k) is not None for k in ("project", "area", "tag", "deadline")
    )
    if has_narrow_filter:
        return rows
    return _merge_overlay(rows, status=status)


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
        rows = r.search(query)
    else:
        import things

        rows = things.search(query)
    return _merge_overlay(rows, query=query, status="incomplete")


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
