"""
Direct SQLite read layer for the Things 3 database.

Provides high-performance read-only access to the Things SQLite database,
bypassing things-py for performance-critical read paths. Falls back to
things-py transparently when the database is unavailable or the schema
version is unrecognised.

Usage:
    reader = get_reader()
    inbox_items = reader.get_inbox()

This module is importable but NOT active until explicitly used. No existing
tools are migrated to use it — it is a foundation for Phase 3 optimisation.

Constraints:
    - Read-only — NEVER writes to the database
    - Uses stdlib sqlite3 only (no new dependencies)
    - Opens in WAL-compatible read-only mode
    - Thread-safe via a single shared connection with serialised access
"""

from __future__ import annotations

import glob as globmod
import logging
import os
import plistlib
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database path detection (mirrors things-py logic)
# ---------------------------------------------------------------------------

_DB_GLOB_31616502 = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    "/ThingsData-*/Things Database.thingsdatabase/main.sqlite"
)
_DB_GLOB_31516502 = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    "/Things Database.thingsdatabase/main.sqlite"
)

_ENV_VAR = "THINGSDB"


def _detect_db_path() -> str | None:
    """Auto-detect the Things database path. Returns *None* if not found."""
    # Environment override
    env_path = os.getenv(_ENV_VAR)
    if env_path:
        if Path(env_path).exists():
            return env_path
        logger.warning("THINGSDB env path does not exist: %s", env_path)
        return None

    # Things 3.15.16+ (versioned data dir)
    try:
        return next(globmod.iglob(os.path.expanduser(_DB_GLOB_31616502)))
    except StopIteration:
        pass

    # Things 3.15.x (non-versioned)
    path = os.path.expanduser(_DB_GLOB_31516502)
    if Path(path).exists():
        return path

    return None


# ---------------------------------------------------------------------------
# Schema constants — derived from things-py's database.py
# ---------------------------------------------------------------------------

# Table names
TABLE_TASK = "TMTask"
TABLE_AREA = "TMArea"
TABLE_TAG = "TMTag"
TABLE_TASKTAG = "TMTaskTag"
TABLE_AREATAG = "TMAreaTag"
TABLE_CHECKLIST_ITEM = "TMChecklistItem"
TABLE_META = "Meta"
TABLE_SETTINGS = "TMSettings"

# Column names for dates (Things-specific binary encoding)
DATE_CREATED = "creationDate"  # REAL: Unix timestamp UTC
DATE_MODIFIED = "userModificationDate"  # REAL: Unix timestamp UTC
DATE_STOP = "stopDate"  # REAL: Unix timestamp UTC
DATE_START = "startDate"  # INTEGER: Things-date binary encoding
DATE_DEADLINE = "deadline"  # INTEGER: Things-date binary encoding

# Status values (TMTask.status)
STATUS_INCOMPLETE = 0
STATUS_CANCELED = 2
STATUS_COMPLETED = 3

# Start values (TMTask.start)
START_INBOX = 0
START_ANYTIME = 1
START_SOMEDAY = 2

# Type values (TMTask.type)
TYPE_TODO = 0
TYPE_PROJECT = 1
TYPE_HEADING = 2

# Minimum schema version we support (matches things-py assertion)
MIN_SCHEMA_VERSION = 22
# Known-good schema versions we have tested against
KNOWN_SCHEMA_VERSIONS = frozenset(range(22, 40))  # conservative range

# ---------------------------------------------------------------------------
# SQL snippets for Things-date ↔ ISO-date conversion
# ---------------------------------------------------------------------------

# Binary masks for Things-date format: YYYYYYYYYYYMMMMDDDDD0000000
_Y_MASK = 0b111111111110000000000000000  # 134152192
_M_MASK = 0b000000000001111000000000000  # 61440
_D_MASK = 0b000000000000000111110000000  # 3968

# Binary masks for Things-time format: hhhhhmmmmmm00000000000000000000
_H_MASK = 0b1111100000000000000000000000000  # 2080374784
_MIN_MASK = 0b0000011111100000000000000000000  # 66060288


def _thingsdate_to_iso_sql(col: str) -> str:
    """SQL expression converting a Things-date column to ISO date string."""
    year = f"({col} & {_Y_MASK}) >> 16"
    month = f"({col} & {_M_MASK}) >> 12"
    day = f"({col} & {_D_MASK}) >> 7"
    iso = f"printf('%d-%02d-%02d', {year}, {month}, {day})"
    return f"CASE WHEN {col} THEN {iso} ELSE NULL END"


def _thingstime_to_iso_sql(col: str) -> str:
    """SQL expression converting a Things-time column to HH:MM string."""
    hours = f"({col} & {_H_MASK}) >> 26"
    minutes = f"({col} & {_MIN_MASK}) >> 20"
    iso = f"printf('%02d:%02d', {hours}, {minutes})"
    return f"CASE WHEN {col} THEN {iso} ELSE NULL END"


def _isodate_to_thingsdate_sql(sql_expr: str) -> str:
    """SQL expression converting an ISO-date SQL expression to Things-date integer."""
    year = f"strftime('%Y', {sql_expr}) << 16"
    month = f"strftime('%m', {sql_expr}) << 12"
    day = f"strftime('%d', {sql_expr}) << 7"
    return f"(({year}) | ({month}) | ({day}))"


# Today's Things-date as a SQL expression (for comparisons)
_TODAY_THINGSDATE = _isodate_to_thingsdate_sql("date('now', 'localtime')")

# ---------------------------------------------------------------------------
# Core task SELECT — mirrors things-py's make_tasks_sql_query
# ---------------------------------------------------------------------------

_TASK_SELECT = f"""
    SELECT DISTINCT
        TASK.uuid,
        CASE
            WHEN TASK.type = {TYPE_TODO} THEN 'to-do'
            WHEN TASK.type = {TYPE_PROJECT} THEN 'project'
            WHEN TASK.type = {TYPE_HEADING} THEN 'heading'
        END AS type,
        CASE
            WHEN TASK.trashed = 1 THEN 1
            ELSE NULL
        END AS trashed,
        TASK.title,
        CASE
            WHEN TASK.status = {STATUS_INCOMPLETE} THEN 'incomplete'
            WHEN TASK.status = {STATUS_CANCELED} THEN 'canceled'
            WHEN TASK.status = {STATUS_COMPLETED} THEN 'completed'
        END AS status,
        CASE WHEN AREA.uuid IS NOT NULL THEN AREA.uuid ELSE NULL END AS area,
        CASE WHEN AREA.uuid IS NOT NULL THEN AREA.title ELSE NULL END AS area_title,
        CASE WHEN PROJECT.uuid IS NOT NULL THEN PROJECT.uuid ELSE NULL END AS project,
        CASE WHEN PROJECT.uuid IS NOT NULL THEN PROJECT.title ELSE NULL END AS project_title,
        CASE WHEN HEADING.uuid IS NOT NULL THEN HEADING.uuid ELSE NULL END AS heading,
        CASE WHEN HEADING.uuid IS NOT NULL THEN HEADING.title ELSE NULL END AS heading_title,
        TASK.notes,
        CASE WHEN TAG.uuid IS NOT NULL THEN 1 ELSE NULL END AS tags,
        CASE
            WHEN TASK.start = {START_INBOX} THEN 'Inbox'
            WHEN TASK.start = {START_ANYTIME} THEN 'Anytime'
            WHEN TASK.start = {START_SOMEDAY} THEN 'Someday'
        END AS start,
        CASE WHEN CHECKLIST_ITEM.uuid IS NOT NULL THEN 1 ELSE NULL END AS checklist,
        {_thingsdate_to_iso_sql(f"TASK.{DATE_START}")} AS start_date,
        {_thingsdate_to_iso_sql(f"TASK.{DATE_DEADLINE}")} AS deadline,
        {_thingstime_to_iso_sql("TASK.reminderTime")} AS reminder_time,
        datetime(TASK.{DATE_STOP}, 'unixepoch', 'localtime') AS stop_date,
        datetime(TASK.{DATE_CREATED}, 'unixepoch', 'localtime') AS created,
        datetime(TASK.{DATE_MODIFIED}, 'unixepoch', 'localtime') AS modified,
        TASK."index",
        TASK.todayIndex AS today_index
    FROM
        {TABLE_TASK} AS TASK
    LEFT OUTER JOIN
        {TABLE_TASK} PROJECT ON TASK.project = PROJECT.uuid
    LEFT OUTER JOIN
        {TABLE_AREA} AREA ON TASK.area = AREA.uuid
    LEFT OUTER JOIN
        {TABLE_TASK} HEADING ON TASK.heading = HEADING.uuid
    LEFT OUTER JOIN
        {TABLE_TASK} PROJECT_OF_HEADING ON HEADING.project = PROJECT_OF_HEADING.uuid
    LEFT OUTER JOIN
        {TABLE_TASKTAG} TAGS ON TASK.uuid = TAGS.tasks
    LEFT OUTER JOIN
        {TABLE_TAG} TAG ON TAGS.tags = TAG.uuid
    LEFT OUTER JOIN
        {TABLE_CHECKLIST_ITEM} CHECKLIST_ITEM ON TASK.uuid = CHECKLIST_ITEM.task
"""

# Common WHERE fragments
_NOT_RECURRING = "TASK.rt1_recurrenceRule IS NULL"
_NOT_TRASHED = "TASK.trashed = 0"
_IS_INCOMPLETE = f"TASK.status = {STATUS_INCOMPLETE}"
_CONTEXT_NOT_TRASHED = (
    "AND NOT IFNULL(PROJECT.trashed, 0) AND NOT IFNULL(PROJECT_OF_HEADING.trashed, 0)"
)

# Columns that should be omitted from results when NULL (matches things-py)
_COLUMNS_TO_OMIT_IF_NONE = frozenset(
    {
        "area",
        "area_title",
        "checklist",
        "heading",
        "heading_title",
        "project",
        "project_title",
        "reminder_time",
        "trashed",
        "tags",
    }
)
# Columns that should be converted to bool when truthy (matches things-py)
_COLUMNS_TO_TRANSFORM_TO_BOOL = frozenset({"checklist", "tags", "trashed"})


# ---------------------------------------------------------------------------
# Row factory (mirrors things-py dict_factory)
# ---------------------------------------------------------------------------


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    """Convert a row to a dict, omitting None columns per things-py convention."""
    result: dict[str, Any] = {}
    for idx, col in enumerate(cursor.description):
        key = col[0]
        value = row[idx]
        if value is None and key in _COLUMNS_TO_OMIT_IF_NONE:
            continue
        if value and key in _COLUMNS_TO_TRANSFORM_TO_BOOL:
            value = bool(value)
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# ThingsSQLiteReader
# ---------------------------------------------------------------------------


class ThingsSQLiteReader:
    """
    Read-only, WAL-compatible reader for the Things 3 SQLite database.

    Thread-safe: uses a single shared connection protected by a lock.
    All public methods fall back to things-py on any database error.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _detect_db_path()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._available = False
        self._schema_version: int | None = None
        self._fallback_reason: str | None = None

        if self._db_path is None:
            self._fallback_reason = "Things database not found"
            logger.warning(
                "SQLite reader: %s — falling back to things-py", self._fallback_reason
            )
            return

        try:
            self._connect()
            self._check_schema()
        except Exception as exc:
            self._fallback_reason = str(exc)
            logger.warning(
                "SQLite reader initialisation failed: %s — falling back to things-py",
                self._fallback_reason,
            )
            self._close()

    # -- connection management ------------------------------------------------

    def _connect(self) -> None:
        """Open a read-only WAL-compatible connection."""
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        # WAL mode pragmas for optimal read performance
        conn.execute("PRAGMA journal_mode=wal")
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000")  # 2 MB page cache
        self._conn = conn
        self._available = True
        logger.info("SQLite reader connected: %s", self._db_path)

    def _close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        self._available = False

    def _check_schema(self) -> None:
        """Verify the database schema is compatible."""
        assert self._conn is not None
        cursor = self._conn.execute(
            f"SELECT value FROM {TABLE_META} WHERE key = 'databaseVersion'"
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Could not read database version from Meta table")

        plist_bytes = row[0].encode()
        version = plistlib.loads(plist_bytes)
        self._schema_version = version

        if version < MIN_SCHEMA_VERSION:
            raise RuntimeError(
                f"Things database schema version {version} is too old (need >= {MIN_SCHEMA_VERSION})"
            )

        if version not in KNOWN_SCHEMA_VERSIONS:
            logger.warning(
                "Things database schema version %d is not in the known-good set (%d–%d). "
                "Proceeding with caution — will fall back to things-py on query errors.",
                version,
                min(KNOWN_SCHEMA_VERSIONS),
                max(KNOWN_SCHEMA_VERSIONS),
            )

        logger.info("Things database schema version: %d", version)

    # -- helpers --------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True if the direct SQLite reader is usable."""
        return self._available and self._conn is not None

    @property
    def schema_version(self) -> int | None:
        return self._schema_version

    def _execute(
        self,
        sql: str,
        params: tuple = (),
        row_factory: Any = None,
    ) -> list[dict[str, Any]] | list[Any]:
        """Execute a read query, returning results as dicts (or via custom factory)."""
        if not self.is_available:
            raise RuntimeError("SQLite reader is not available")

        with self._lock:
            assert self._conn is not None
            self._conn.row_factory = row_factory or _dict_factory
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def _execute_with_fallback(
        self,
        sql: str,
        params: tuple,
        fallback_fn,
        *,
        row_factory: Any = None,
    ):
        """
        Try direct SQLite; on failure call fallback_fn() instead.

        The fallback is a zero-argument callable that returns the same shape.
        """
        if not self.is_available:
            return fallback_fn()

        try:
            return self._execute(sql, params, row_factory=row_factory)
        except Exception as exc:
            logger.warning(
                "SQLite reader query failed, falling back to things-py: %s", exc
            )
            return fallback_fn()

    # -- tag resolution (needed for task results) -----------------------------

    def _get_tags_for_task(self, task_uuid: str) -> list[str]:
        """Return tag titles for a single task."""
        sql = f"""
            SELECT TAG.title
            FROM {TABLE_TASKTAG} AS TT
            LEFT OUTER JOIN {TABLE_TAG} TAG ON TAG.uuid = TT.tags
            WHERE TT.tasks = ?
            ORDER BY TAG."index"
        """
        rows = self._execute(sql, (task_uuid,), row_factory=lambda _c, r: r[0])
        return rows

    def _enrich_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add tag lists to tasks that have tags=True (matches things-py behaviour)."""
        for task in tasks:
            if task.get("tags"):
                task["tags"] = self._get_tags_for_task(task["uuid"])
        return tasks

    # -- public read API ------------------------------------------------------

    def get_inbox(self) -> list[dict[str, Any]]:
        """Items in the Inbox (start=0, incomplete, not trashed, not recurring)."""
        sql = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_INBOX}
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.inbox()

        result = self._execute_with_fallback(sql, (), _fallback)
        return self._enrich_tasks(result)

    def get_today(self) -> list[dict[str, Any]]:
        """
        Items in Today view.

        Mirrors things-py logic: regular today tasks + unconfirmed scheduled
        tasks with past start dates + unconfirmed overdue deadlines.
        """
        # Regular today tasks: start=Anytime, has start_date, incomplete
        sql_regular = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_ANYTIME}
                AND TASK.{DATE_START} IS NOT NULL
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK.todayIndex
        """
        # Unconfirmed scheduled: start=Someday, start_date in past
        sql_scheduled = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_SOMEDAY}
                AND TASK.{DATE_START} IS NOT NULL
                AND TASK.{DATE_START} <= {_TODAY_THINGSDATE}
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK.todayIndex
        """
        # Unconfirmed overdue: no start_date, has deadline in past, not suppressed
        sql_overdue = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.{DATE_START} IS NULL
                AND TASK.{DATE_DEADLINE} IS NOT NULL
                AND TASK.{DATE_DEADLINE} <= {_TODAY_THINGSDATE}
                AND TASK.deadlineSuppressionDate IS NULL
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.today()

        if not self.is_available:
            return _fallback()

        try:
            regular = self._execute(sql_regular, ())
            scheduled = self._execute(sql_scheduled, ())
            overdue = self._execute(sql_overdue, ())
            result = [*regular, *scheduled, *overdue]
            result.sort(
                key=lambda t: (t.get("today_index", 0) or 0, t.get("start_date") or "")
            )
            return self._enrich_tasks(result)
        except Exception as exc:
            logger.warning("SQLite reader get_today failed: %s", exc)
            return _fallback()

    def get_upcoming(self) -> list[dict[str, Any]]:
        """Items with a future start date and start=Someday."""
        sql = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_SOMEDAY}
                AND TASK.{DATE_START} IS NOT NULL
                AND TASK.{DATE_START} > {_TODAY_THINGSDATE}
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.upcoming()

        result = self._execute_with_fallback(sql, (), _fallback)
        return self._enrich_tasks(result)

    def get_anytime(self) -> list[dict[str, Any]]:
        """Items with start=Anytime."""
        sql = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_ANYTIME}
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.anytime()

        result = self._execute_with_fallback(sql, (), _fallback)
        return self._enrich_tasks(result)

    def get_someday(self) -> list[dict[str, Any]]:
        """Items with start=Someday and no start_date."""
        sql = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND TASK.start = {START_SOMEDAY}
                AND TASK.{DATE_START} IS NULL
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.someday()

        result = self._execute_with_fallback(sql, (), _fallback)
        return self._enrich_tasks(result)

    def get_todos(
        self,
        *,
        status: str | None = None,
        project: str | None = None,
        area: str | None = None,
        tag: str | None = None,
        deadline: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Filtered to-do query.

        Parameters match the things-py conventions:
            status: 'incomplete' (default), 'completed', 'canceled', or None (any)
            project: UUID string to filter by project
            area: UUID string to filter by area
            tag: tag title string to filter by tag
            deadline: True = has deadline, False = no deadline, None = any
        """
        conditions = [
            _NOT_RECURRING,
            _NOT_TRASHED,
            f"TASK.type = {TYPE_TODO}",
        ]
        params: list[Any] = []

        # Status filter
        status_map = {
            "incomplete": STATUS_INCOMPLETE,
            "completed": STATUS_COMPLETED,
            "canceled": STATUS_CANCELED,
            None: None,
        }
        if status is not None:
            status_val = status_map.get(status)
            if status_val is None:
                raise ValueError(f"Invalid status: {status!r}")
            conditions.append(f"TASK.status = {status_val}")
        else:
            # Default to incomplete (matches things-py default)
            conditions.append(f"TASK.status = {STATUS_INCOMPLETE}")

        if project is not None:
            conditions.append("(TASK.project = ? OR PROJECT_OF_HEADING.uuid = ?)")
            params.extend([project, project])

        if area is not None:
            conditions.append("TASK.area = ?")
            params.append(area)

        if tag is not None:
            conditions.append("TAG.title = ?")
            params.append(tag)

        if deadline is True:
            conditions.append(f"TASK.{DATE_DEADLINE} IS NOT NULL")
        elif deadline is False:
            conditions.append(f"TASK.{DATE_DEADLINE} IS NULL")

        conditions.append("NOT IFNULL(PROJECT.trashed, 0)")
        conditions.append("NOT IFNULL(PROJECT_OF_HEADING.trashed, 0)")

        where = " AND ".join(conditions)
        sql = f"""
            {_TASK_SELECT}
            WHERE {where}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            kwargs: dict[str, Any] = {"type": "to-do"}
            if status is not None:
                kwargs["status"] = status
            if project is not None:
                kwargs["project"] = project
            if area is not None:
                kwargs["area"] = area
            if tag is not None:
                kwargs["tag"] = tag
            if deadline is not None:
                kwargs["deadline"] = deadline
            return things.tasks(**kwargs)

        result = self._execute_with_fallback(sql, tuple(params), _fallback)
        return self._enrich_tasks(result)

    def get_projects(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """
        Project list.

        Parameters:
            status: 'incomplete' (default), 'completed', 'canceled', or None
        """
        conditions = [
            _NOT_RECURRING,
            _NOT_TRASHED,
            f"TASK.type = {TYPE_PROJECT}",
        ]

        status_map = {
            "incomplete": STATUS_INCOMPLETE,
            "completed": STATUS_COMPLETED,
            "canceled": STATUS_CANCELED,
            None: None,
        }
        if status is not None:
            status_val = status_map.get(status)
            if status_val is None:
                raise ValueError(f"Invalid status: {status!r}")
            conditions.append(f"TASK.status = {status_val}")
        else:
            conditions.append(f"TASK.status = {STATUS_INCOMPLETE}")

        where = " AND ".join(conditions)
        sql = f"""
            {_TASK_SELECT}
            WHERE {where}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            kwargs: dict[str, Any] = {}
            if status is not None:
                kwargs["status"] = status
            return things.projects(**kwargs)

        result = self._execute_with_fallback(sql, (), _fallback)
        return self._enrich_tasks(result)

    def get_areas(self) -> list[dict[str, Any]]:
        """All areas."""
        sql = f"""
            SELECT DISTINCT
                AREA.uuid,
                'area' AS type,
                AREA.title,
                CASE
                    WHEN AREA_TAG.areas IS NOT NULL THEN 1
                    ELSE NULL
                END AS tags
            FROM
                {TABLE_AREA} AS AREA
            LEFT OUTER JOIN
                {TABLE_AREATAG} AREA_TAG ON AREA_TAG.areas = AREA.uuid
            LEFT OUTER JOIN
                {TABLE_TAG} TAG ON TAG.uuid = AREA_TAG.tags
            ORDER BY AREA."index"
        """

        def _fallback():
            import things

            return things.areas()

        def _area_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for idx, col in enumerate(cursor.description):
                key = col[0]
                value = row[idx]
                if value is None and key in _COLUMNS_TO_OMIT_IF_NONE:
                    continue
                if value and key in _COLUMNS_TO_TRANSFORM_TO_BOOL:
                    value = bool(value)
                result[key] = value
            return result

        result = self._execute_with_fallback(
            sql, (), _fallback, row_factory=_area_factory
        )

        # Enrich areas with tag lists (matches things-py)
        for area in result:
            if area.get("tags"):
                tag_sql = f"""
                    SELECT TAG.title
                    FROM {TABLE_AREATAG} AS AT
                    LEFT OUTER JOIN {TABLE_TAG} TAG ON TAG.uuid = AT.tags
                    WHERE AT.areas = ?
                    ORDER BY TAG."index"
                """
                try:
                    area["tags"] = self._execute(
                        tag_sql, (area["uuid"],), row_factory=lambda _c, r: r[0]
                    )
                except Exception:
                    pass  # leave tags as True on failure

        return result

    def search(self, query: str) -> list[dict[str, Any]]:
        """
        Search tasks by title and notes using LIKE.

        Uses parameterised queries to prevent SQL injection.
        """
        if not query:
            return []

        like_pattern = f"%{query}%"
        sql = f"""
            {_TASK_SELECT}
            WHERE
                {_NOT_RECURRING}
                AND {_NOT_TRASHED}
                AND {_IS_INCOMPLETE}
                AND (
                    TASK.title LIKE ?
                    OR TASK.notes LIKE ?
                    OR AREA.title LIKE ?
                )
                {_CONTEXT_NOT_TRASHED}
            ORDER BY TASK."index"
        """

        def _fallback():
            import things

            return things.search(query)

        result = self._execute_with_fallback(
            sql, (like_pattern, like_pattern, like_pattern), _fallback
        )
        return self._enrich_tasks(result)

    def get_tags(self) -> list[dict[str, Any]]:
        """All tags."""
        sql = f"""
            SELECT uuid, 'tag' AS type, title, shortcut
            FROM {TABLE_TAG}
            ORDER BY "index"
        """

        def _tag_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
            return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

        def _fallback():
            import things

            return things.tags()

        return self._execute_with_fallback(sql, (), _fallback, row_factory=_tag_factory)

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """Explicitly close the database connection."""
        self._close()

    def __del__(self) -> None:
        self._close()

    def __repr__(self) -> str:
        status = (
            "available"
            if self.is_available
            else f"unavailable ({self._fallback_reason})"
        )
        return f"<ThingsSQLiteReader {status} path={self._db_path!r} schema={self._schema_version}>"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_reader: ThingsSQLiteReader | None = None
_reader_lock = threading.Lock()


def get_reader() -> ThingsSQLiteReader:
    """
    Get or create the singleton ThingsSQLiteReader.

    Safe to call from any thread. Initialisation happens once.
    """
    global _reader
    if _reader is not None:
        return _reader

    with _reader_lock:
        # Double-check after acquiring lock
        if _reader is not None:
            return _reader
        _reader = ThingsSQLiteReader()
        return _reader


def reset_reader() -> None:
    """Close and reset the singleton (useful for testing)."""
    global _reader
    with _reader_lock:
        if _reader is not None:
            _reader.close()
            _reader = None
