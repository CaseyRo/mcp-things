"""Unified read interface — SQLite reader with things-py fallback.

This module provides a drop-in API matching the things-py calling conventions
so tools can switch from `import things; things.inbox()` to
`from .reader import reader; reader.inbox()` with no other changes.

The SQLite reader is preferred for performance; things-py is the fallback.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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


# Waits between read-back attempts after a URL-scheme create (CDI-1588). Things
# commits the new row a moment after `open` returns (see CDI-1255), so poll
# briefly; the sum is the confirmation window.
READBACK_DELAYS = (0.25, 0.25, 0.5, 0.5, 1.0, 1.0)


async def read_back(titles: list[str], since: float) -> dict[str, dict[str, Any]]:
    """Find just-created to-dos by exact title + creation time (CDI-1588).

    The URL scheme returns no UUID, so after a create we look for the newest
    to-do with that exact title created at/after ``since``. Returns
    ``{title: row}`` for each title confirmed within the window; a missing title
    means "created, not yet confirmed", never "failed".

    ponytail: two creates with the same title inside one window both resolve
    to the newest row; match on more fields if that ever matters.
    """
    r = _get_sqlite_reader()
    found: dict[str, dict[str, Any]] = {}
    if not (r and r.is_available):
        return found
    wanted = set(titles)
    for delay in READBACK_DELAYS:
        await asyncio.sleep(delay)
        for title in wanted - found.keys():
            try:
                row = r.find_created(title, since)
            except Exception:
                logger.debug("reader: read-back query failed (non-critical)")
                return found
            if row:
                found[title] = row
        if found.keys() == wanted:
            break
    return found


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
def get(uuid: str) -> dict[str, Any] | None:
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


def logbook_with_notes(fragment: str) -> list[dict[str, Any]]:
    """Completed to-dos whose notes contain ``fragment`` (repeat sweep, CDI-2076)."""
    r = _get_sqlite_reader()
    if r:
        return r.get_completed_with_notes(fragment)
    import things

    return [
        t
        for t in things.todos(status="completed")
        if fragment in (t.get("notes") or "")
    ]


def is_native_repeat(uuid: str) -> bool:
    """True if Things itself repeats this to-do (template or copy)."""
    r = _get_sqlite_reader()
    return bool(r and r.is_native_repeat(uuid))


def logbook() -> list[dict[str, Any]]:
    """Get logbook items — uses things-py."""
    import things

    if hasattr(things, "logbook"):
        return things.logbook()
    return things.last("7d", status="completed")
