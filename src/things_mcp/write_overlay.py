"""In-process write overlay for read-your-writes consistency (CDI-1255).

Things 3 creates items via the URL scheme / AppleScript against the *live* app
state, but the read path (``reader`` -> ``sqlite_reader``) queries the on-disk
``main.sqlite`` store. Things does not flush newly created items to disk
immediately, so a task captured a moment ago is invisible to ``search-tasks`` /
``get-tasks`` / fuzzy ``task_title`` lookups until the kernel syncs — a
read-your-writes inconsistency that surfaces as a confident false "No task
found".

This module maintains a short-lived, thread-safe, in-process overlay of items
the server itself just wrote. The URL/JSON scheme returns no UUID, so entries
are keyed by a synthetic id and matched against reads by title (the only field
we reliably know at write time). Reads merge overlay entries that are not yet
present in the SQLite snapshot, giving same-session read-your-writes correctness
without depending on AppleScript read latency.

Design notes:
    - TTL-bounded (default 90s). Entries expire automatically; once SQLite has
      caught up the real row wins (we de-dupe by title so the overlay never
      double-counts).
    - We also record the Things SQLite file mtime at write time. A read can ask
      ``is_index_stale()`` to learn whether a write happened more recently than
      the database file was last modified — i.e. whether a "not found" is
      trustworthy or merely an un-flushed write. This powers the staleness-aware
      "not found" signalling (ticket option #4).
    - Synthetic ids use an ``overlay:`` prefix so consumers can tell a
      not-yet-persisted item from a real Things UUID and avoid trying to mutate
      it by id (the URL scheme would reject it).

The overlay is intentionally best-effort: any failure to record is swallowed by
callers (a write that succeeded must never be reported as failed just because
the overlay bookkeeping raised).
"""

from __future__ import annotations

import threading
import time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any

from .logging_config import get_logger

logger = get_logger(__name__)

# How long an un-persisted write stays visible in the overlay, in seconds.
# Generous enough to cover Things' on-disk flush latency, short enough that a
# canceled/renamed item does not linger misleadingly.
DEFAULT_TTL_SECONDS = 90

# Prefix marking a synthetic, not-yet-persisted id.
OVERLAY_ID_PREFIX = "overlay:"


def is_overlay_id(value: str | None) -> bool:
    """True if ``value`` is a synthetic overlay id rather than a real Things UUID."""
    return bool(value) and value.startswith(OVERLAY_ID_PREFIX)


@dataclass
class OverlayEntry:
    """A single just-written item awaiting SQLite persistence."""

    uuid: str
    title: str
    created_at: float
    db_mtime_at_write: float | None = None
    when: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    start: str | None = None  # "Inbox" / "Anytime" / "Someday" etc.

    def as_todo_row(self) -> dict[str, Any]:
        """Render this entry in the things-py row shape reads expect.

        Marked ``_overlay: True`` so downstream code (and tests) can recognise a
        provisional row, and ``status: incomplete`` since a freshly captured item
        is always incomplete.
        """
        row: dict[str, Any] = {
            "uuid": self.uuid,
            "title": self.title,
            "type": "to-do",
            "status": "incomplete",
            "start": self.start or "Inbox",
            "_overlay": True,
        }
        if self.notes:
            row["notes"] = self.notes
        if self.tags:
            row["tags"] = list(self.tags)
        if self.when:
            row["start_date"] = None  # we don't resolve relative dates here
        return row


class WriteOverlay:
    """Thread-safe TTL store of just-written items, keyed by synthetic id."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._entries: dict[str, OverlayEntry] = {}
        self._lock = threading.Lock()
        # Wall-clock of the most recent successful write recorded here. Used to
        # decide whether the SQLite snapshot is behind a recent write.
        self._last_write_at: float = 0.0

    # -- recording ------------------------------------------------------------

    def record(
        self,
        title: str,
        *,
        when: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> str:
        """Record a just-written item and return its synthetic overlay id.

        ``title`` is required; everything else is best-effort metadata so the
        provisional row reads sensibly. The synthetic id is returned so a caller
        could surface it, but it MUST NOT be used to mutate the item by id.
        """
        if not title:
            raise ValueError("title is required to record a write")

        synthetic_id = f"{OVERLAY_ID_PREFIX}{_uuid.uuid4().hex}"
        start = "Anytime" if when and when not in ("someday",) else None
        if when == "someday":
            start = "Someday"
        entry = OverlayEntry(
            uuid=synthetic_id,
            title=title,
            created_at=time.time(),
            db_mtime_at_write=_safe_db_mtime(),
            when=when,
            tags=list(tags or []),
            notes=notes,
            start=start,
        )
        with self._lock:
            self._entries[synthetic_id] = entry
            self._last_write_at = entry.created_at
        logger.debug("write_overlay: recorded provisional item (ttl=%ds)", self._ttl)
        return synthetic_id

    # -- querying -------------------------------------------------------------

    def _live_entries(self) -> list[OverlayEntry]:
        """Return non-expired entries, pruning expired ones under the lock."""
        now = time.time()
        with self._lock:
            expired = [
                k for k, e in self._entries.items() if now - e.created_at > self._ttl
            ]
            for k in expired:
                del self._entries[k]
            return list(self._entries.values())

    def overlay_rows(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return provisional rows matching the given read.

        Args:
            query: case-insensitive substring matched against title (and notes),
                mirroring ``reader.search``. ``None`` matches everything.
            status: only ``None`` or ``"incomplete"`` yields overlay rows —
                provisional items are always incomplete, so a request for
                completed/canceled never matches the overlay.
        """
        if status not in (None, "incomplete"):
            return []
        rows: list[dict[str, Any]] = []
        q = query.lower() if query else None
        for entry in self._live_entries():
            if q is not None:
                haystack = entry.title.lower()
                if entry.notes:
                    haystack += " " + entry.notes.lower()
                if q not in haystack:
                    continue
            rows.append(entry.as_todo_row())
        return rows

    def merge_into(
        self,
        rows: list[dict[str, Any]],
        *,
        query: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Append overlay rows to ``rows`` for any provisional item not already present.

        De-dupes by (lowercased) title: once Things flushes the real row to
        SQLite, the persisted row is authoritative and the overlay row is
        suppressed, so a freshly captured item is never double-counted.
        """
        overlay = self.overlay_rows(query=query, status=status)
        if not overlay:
            return rows
        existing_titles = {
            (r.get("title") or "").strip().lower() for r in rows if r.get("title")
        }
        merged = list(rows)
        for orow in overlay:
            title_key = (orow.get("title") or "").strip().lower()
            if title_key and title_key in existing_titles:
                continue
            merged.append(orow)
            existing_titles.add(title_key)
        return merged

    # -- staleness ------------------------------------------------------------

    def has_recent_writes(self) -> bool:
        """True if any non-expired provisional write is still tracked."""
        return bool(self._live_entries())

    def is_index_stale(self) -> bool:
        """True if a write happened more recently than SQLite was last flushed.

        Combines wall-clock recency with the DB file mtime captured at write
        time (ticket option #3). If the live database file has not been modified
        since our most recent write, the on-disk snapshot is behind that write
        and a "not found" result may be a false negative.

        Returns False when there are no recent writes, so a genuinely empty
        search is reported as authoritative rather than "maybe stale".
        """
        if not self.has_recent_writes():
            return False
        current_mtime = _safe_db_mtime()
        if current_mtime is None:
            # Can't read the DB mtime — be conservative and flag staleness while
            # any recent write is still tracked.
            return True
        # If every tracked write predates (or equals) the current DB mtime, the
        # DB has caught up and we are not stale.
        for entry in self._live_entries():
            base = entry.db_mtime_at_write
            if base is None:
                return True
            # The DB file mtime has not advanced past this write -> still behind.
            if current_mtime <= base:
                return True
        return False

    # -- lifecycle ------------------------------------------------------------

    def clear(self) -> None:
        """Drop all tracked entries (used by tests)."""
        with self._lock:
            self._entries.clear()
            self._last_write_at = 0.0


def _safe_db_mtime() -> float | None:
    """Return the Things SQLite file mtime, or None if it can't be determined."""
    try:
        from .sqlite_reader import _detect_db_path

        path = _detect_db_path()
        if not path:
            return None
        import os

        return os.path.getmtime(path)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_overlay: WriteOverlay | None = None
_overlay_lock = threading.Lock()


def get_overlay() -> WriteOverlay:
    """Get or create the process-wide write overlay singleton."""
    global _overlay
    if _overlay is not None:
        return _overlay
    with _overlay_lock:
        if _overlay is not None:
            return _overlay
        _overlay = WriteOverlay()
        return _overlay


def record_write(
    title: str,
    *,
    when: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> str | None:
    """Best-effort convenience wrapper used by write tools after a successful write.

    Never raises: a bookkeeping failure must not turn a successful write into a
    reported failure. Returns the synthetic id, or None on failure.
    """
    try:
        return get_overlay().record(title, when=when, tags=tags, notes=notes)
    except Exception:
        logger.debug("write_overlay: failed to record write (non-critical)")
        return None
