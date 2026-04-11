"""Tests for SQLite reader checklist enrichment."""

import sqlite3
import plistlib

import pytest

from things_mcp.sqlite_reader import (
    ThingsSQLiteReader,
    TABLE_TASK,
    TABLE_AREA,
    TABLE_TAG,
    TABLE_TASKTAG,
    TABLE_AREATAG,
    TABLE_CHECKLIST_ITEM,
    TABLE_META,
    STATUS_INCOMPLETE,
    STATUS_COMPLETED,
    START_ANYTIME,
    START_INBOX,
    TYPE_TODO,
)

pytestmark = [pytest.mark.unit]


def _things_date(year: int, month: int, day: int) -> int:
    """Encode a date as a Things-format integer."""
    return (year << 16) | (month << 12) | (day << 7)


@pytest.fixture
def test_db(tmp_path):
    """Create a minimal Things-like SQLite database for testing."""
    db_path = str(tmp_path / "main.sqlite")
    conn = sqlite3.connect(db_path)
    # Enable WAL mode before the reader opens it read-only
    conn.execute("PRAGMA journal_mode=wal")

    # Create schema
    conn.executescript(f"""
        CREATE TABLE {TABLE_META} (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE {TABLE_TASK} (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            notes TEXT,
            type INTEGER DEFAULT {TYPE_TODO},
            status INTEGER DEFAULT {STATUS_INCOMPLETE},
            start INTEGER DEFAULT {START_ANYTIME},
            trashed INTEGER DEFAULT 0,
            area TEXT,
            project TEXT,
            heading TEXT,
            startDate INTEGER,
            deadline INTEGER,
            stopDate REAL,
            creationDate REAL DEFAULT 0,
            userModificationDate REAL DEFAULT 0,
            "index" INTEGER DEFAULT 0,
            todayIndex INTEGER DEFAULT 0,
            reminderTime INTEGER,
            rt1_recurrenceRule TEXT,
            deadlineSuppressionDate TEXT,
            leavesTombstone INTEGER DEFAULT 0
        );
        CREATE TABLE {TABLE_AREA} (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            "index" INTEGER DEFAULT 0
        );
        CREATE TABLE {TABLE_TAG} (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            shortcut TEXT,
            "index" INTEGER DEFAULT 0
        );
        CREATE TABLE {TABLE_TASKTAG} (
            tasks TEXT,
            tags TEXT
        );
        CREATE TABLE {TABLE_AREATAG} (
            areas TEXT,
            tags TEXT
        );
        CREATE TABLE {TABLE_CHECKLIST_ITEM} (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            status INTEGER DEFAULT {STATUS_INCOMPLETE},
            stopDate REAL,
            creationDate REAL DEFAULT 1700000000,
            userModificationDate REAL DEFAULT 1700000000,
            "index" INTEGER DEFAULT 0,
            task TEXT,
            leavesTombstone INTEGER DEFAULT 0,
            experimental BLOB
        );
    """)

    # Insert schema version as plist (Things uses plist-encoded version)
    version_plist = plistlib.dumps(26, fmt=plistlib.FMT_XML).decode()
    conn.execute(
        f"INSERT INTO {TABLE_META} (key, value) VALUES (?, ?)",
        ("databaseVersion", version_plist),
    )

    conn.commit()
    yield conn, db_path
    conn.close()


def _insert_task(conn, uuid, title, **kwargs):
    """Insert a task with sensible defaults."""
    defaults = {
        "type": TYPE_TODO,
        "status": STATUS_INCOMPLETE,
        "start": START_ANYTIME,
        "trashed": 0,
        "creationDate": 1700000000,
        "userModificationDate": 1700000000,
        "index": 0,
    }
    defaults.update(kwargs)
    cols = ["uuid", "title"] + list(defaults.keys())
    vals = [uuid, title] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(f'"{c}"' if c == "index" else c for c in cols)
    conn.execute(
        f"INSERT INTO {TABLE_TASK} ({col_names}) VALUES ({placeholders})", vals
    )
    conn.commit()


def _insert_checklist_item(
    conn, uuid, task_uuid, title, index=0, status=STATUS_INCOMPLETE, stop_date=None
):
    """Insert a checklist item."""
    conn.execute(
        f"""INSERT INTO {TABLE_CHECKLIST_ITEM}
            (uuid, title, status, stopDate, creationDate, userModificationDate, "index", task)
            VALUES (?, ?, ?, ?, 1700000000, 1700000000, ?, ?)""",
        (uuid, title, status, stop_date, index, task_uuid),
    )
    conn.commit()


class TestChecklistEnrichment:
    """Tests for checklist item enrichment in the SQLite reader."""

    def test_task_with_checklist_items(self, test_db):
        """Tasks with checklist items get a list of item dicts."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "My Task")
        _insert_checklist_item(conn, "cl-1", "task-1", "Step one", index=0)
        _insert_checklist_item(conn, "cl-2", "task-1", "Step two", index=1)

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()

        assert len(tasks) == 1
        checklist = tasks[0]["checklist"]
        assert isinstance(checklist, list)
        assert len(checklist) == 2
        assert checklist[0]["title"] == "Step one"
        assert checklist[1]["title"] == "Step two"

    def test_checklist_item_format(self, test_db):
        """Each checklist item dict has the expected keys."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "My Task")
        _insert_checklist_item(conn, "cl-1", "task-1", "A step")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()
        item = tasks[0]["checklist"][0]

        assert item["uuid"] == "cl-1"
        assert item["title"] == "A step"
        assert item["status"] == "incomplete"
        assert item["type"] == "checklist-item"
        assert "created" in item
        assert "modified" in item

    def test_checklist_completed_status(self, test_db):
        """Completed checklist items have status='completed'."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "My Task")
        _insert_checklist_item(
            conn,
            "cl-1",
            "task-1",
            "Done step",
            status=STATUS_COMPLETED,
            stop_date=1700100000,
        )
        _insert_checklist_item(
            conn, "cl-2", "task-1", "Open step", status=STATUS_INCOMPLETE
        )

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()
        checklist = tasks[0]["checklist"]

        assert checklist[0]["status"] == "completed"
        assert checklist[1]["status"] == "incomplete"

    def test_checklist_ordering(self, test_db):
        """Checklist items are returned in index order."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "My Task")
        # Insert out of order
        _insert_checklist_item(conn, "cl-3", "task-1", "Third", index=2)
        _insert_checklist_item(conn, "cl-1", "task-1", "First", index=0)
        _insert_checklist_item(conn, "cl-2", "task-1", "Second", index=1)

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()
        titles = [item["title"] for item in tasks[0]["checklist"]]

        assert titles == ["First", "Second", "Third"]

    def test_task_without_checklist(self, test_db):
        """Tasks without checklist items have no 'checklist' key (omitted)."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "Plain Task")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()

        assert len(tasks) == 1
        # checklist key should be omitted (not present) per _COLUMNS_TO_OMIT_IF_NONE
        assert "checklist" not in tasks[0]

    def test_checklist_per_task_isolation(self, test_db):
        """Each task gets only its own checklist items."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "Task A", **{"index": 0})
        _insert_task(conn, "task-2", "Task B", **{"index": 1})
        _insert_checklist_item(conn, "cl-a1", "task-1", "A step 1")
        _insert_checklist_item(conn, "cl-a2", "task-1", "A step 2")
        _insert_checklist_item(conn, "cl-b1", "task-2", "B step 1")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_anytime()

        task_a = next(t for t in tasks if t["uuid"] == "task-1")
        task_b = next(t for t in tasks if t["uuid"] == "task-2")

        assert len(task_a["checklist"]) == 2
        assert len(task_b["checklist"]) == 1
        assert task_b["checklist"][0]["title"] == "B step 1"

    def test_checklist_in_inbox(self, test_db):
        """Checklist enrichment works for inbox tasks too."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "Inbox Task", start=START_INBOX)
        _insert_checklist_item(conn, "cl-1", "task-1", "Check this")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_inbox()

        assert len(tasks) == 1
        assert isinstance(tasks[0]["checklist"], list)
        assert tasks[0]["checklist"][0]["title"] == "Check this"

    def test_checklist_in_search(self, test_db):
        """Checklist enrichment works for search results."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "Searchable Task")
        _insert_checklist_item(conn, "cl-1", "task-1", "Sub item")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.search("Searchable")

        assert len(tasks) == 1
        assert isinstance(tasks[0]["checklist"], list)
        assert tasks[0]["checklist"][0]["title"] == "Sub item"

    def test_checklist_in_todos_filter(self, test_db):
        """Checklist enrichment works for filtered get_todos()."""
        conn, db_path = test_db
        _insert_task(conn, "task-1", "Filtered Task")
        _insert_checklist_item(conn, "cl-1", "task-1", "Step A")

        reader = ThingsSQLiteReader(db_path)
        tasks = reader.get_todos(status="incomplete")

        assert len(tasks) == 1
        assert isinstance(tasks[0]["checklist"], list)
        assert tasks[0]["checklist"][0]["title"] == "Step A"
