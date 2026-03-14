"""Triage Tracker: Records and analyzes inbox triage patterns.

Tracks every triage action (complete, cancel, defer, schedule, etc.) with
anonymized metadata. No task titles, notes, or personal content is stored —
only computed categories, action types, and timestamps.

Privacy by design: categorization runs at record time, only the result is persisted.
"""

import json
import stat
import threading
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)

# Default data directory (matches DLQ and config patterns)
DATA_DIR = Path.home() / ".things-mcp"
HISTORY_FILE = DATA_DIR / "triage_history.json"


def categorize_task(
    title: str, notes: Optional[str] = None, tags: Optional[list[str]] = None
) -> tuple[str, float]:
    """Classify a task into a category using heuristic rules.

    Pure function — no side effects, no network, no LLM.
    Returns (category, confidence). First matching rule wins.

    Designed to be replaceable with an LLM call later (same signature).

    Args:
        title: Task title
        notes: Task notes (optional)
        tags: Task tags (optional)

    Returns:
        Tuple of (category string, confidence float 0-1)
    """
    title_lower = (title or "").lower()
    notes_lower = (notes or "").lower()
    combined = f"{title_lower} {notes_lower}"
    tags = tags or []

    # Rule 1: GitHub/GitLab URL
    if "github.com" in combined or "gitlab.com" in combined:
        return ("repo-research", 0.9)

    # Rule 2: Any URL
    if "http://" in combined or "https://" in combined:
        return ("web-reference", 0.85)

    # Rule 3: Person name pattern (e.g., "Marcel: ...", "Alice - ...")
    import re

    if re.match(r"^[A-Z][a-z]+[\s]*[:\-–—]", title or ""):
        return ("client-person", 0.7)

    # Rule 4: Waiting-for tag
    if "waiting-for" in tags:
        return ("delegation", 0.9)

    # Rule 5: Follow-up language
    if any(w in title_lower for w in ["review", "check", "follow up", "follow-up"]):
        return ("follow-up", 0.7)

    # Rule 6: Purchase language
    if any(w in title_lower for w in ["buy", "order", "purchase"]):
        return ("purchase", 0.75)

    # Rule 7: Vague capture — short title, no notes
    if not notes and len(title or "") < 30:
        return ("vague-capture", 0.6)

    # Rule 8: Default
    return ("general", 0.5)


class TriageTracker:
    """Tracks triage actions and provides trend analysis.

    Records are anonymized: no task titles, notes, or tags are stored.
    Only the computed category, action, timestamp, and task_id are persisted.

    Thread-safe via a lock that wraps all load+modify+save operations.
    """

    def __init__(self, history_file: Optional[Path] = None):
        self._file = history_file or HISTORY_FILE
        self._lock = threading.Lock()
        self._last_inbox_view: Optional[datetime] = None
        self._current_session_id: Optional[str] = None
        self._session_start: Optional[datetime] = None

    def record_inbox_view(self) -> None:
        """Track when process-inbox was called (for source detection)."""
        now = datetime.now()
        self._last_inbox_view = now

        # Start a new session if none active or last one was >5 min ago
        if (
            self._session_start is None
            or (now - self._session_start).total_seconds() > 300
        ):
            self._current_session_id = str(uuid.uuid4())[:8]
            self._session_start = now

    def record(
        self,
        task_id: str,
        task_title: str,
        task_notes: Optional[str] = None,
        task_tags: Optional[list[str]] = None,
        action: str = "modified",
        action_details: Optional[dict] = None,
    ) -> None:
        """Record a triage action. Categorizes at write time, stores only the result.

        Args:
            task_id: Things UUID of the task
            task_title: Task title (used for categorization only, NOT stored)
            task_notes: Task notes (used for categorization only, NOT stored)
            task_tags: Task tags (used for categorization only, NOT stored)
            action: Action taken (completed, canceled, deferred-someday, etc.)
            action_details: Optional extra context (e.g., defer_to value)
        """
        now = datetime.now()

        # Categorize using heuristics (title/notes are processed but not stored)
        category, confidence = categorize_task(task_title, task_notes, task_tags)

        # Detect source: was process-inbox called recently?
        source = "direct"
        if self._last_inbox_view:
            elapsed = (now - self._last_inbox_view).total_seconds()
            if elapsed < 60:
                source = "process-inbox"

        # Redact PII from action_details before storage
        safe_details = dict(action_details or {})
        if "delegated_to" in safe_details:
            safe_details["delegated_to"] = "[redacted]"

        record = {
            "record_id": str(uuid.uuid4()),
            "timestamp": now.isoformat(),
            "task_id": task_id,
            "action": action,
            "action_details": safe_details,
            "category": category,
            "category_confidence": confidence,
            "source": source,
            "session_id": self._current_session_id,
        }

        with self._lock:
            records = self._load()
            records.append(record)
            self._save(records)

    def get_records(
        self,
        days: int = 7,
        action: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        """Get filtered triage records.

        Args:
            days: Number of days to look back (0 = all records)
            action: Filter by action type
            category: Filter by category
        """
        with self._lock:
            records = self._load()

        if days > 0:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            records = [r for r in records if r.get("timestamp", "") >= cutoff]

        if action:
            records = [r for r in records if r.get("action") == action]

        if category:
            records = [r for r in records if r.get("category") == category]

        return records

    def get_summary(self, days: int = 7) -> dict:
        """Get summary statistics for the given period.

        Returns dict with: total, actions, categories, daily_counts,
        sessions, avg_per_day, busiest_day.
        """
        records = self.get_records(days=days)

        if not records:
            return {
                "total": 0,
                "actions": {},
                "categories": {},
                "daily_counts": {},
                "sessions": 0,
                "avg_per_day": 0.0,
                "busiest_day": None,
                "no_context_cancel_rate": 0.0,
            }

        # Action breakdown
        actions: dict[str, int] = {}
        for r in records:
            a = r.get("action", "unknown")
            actions[a] = actions.get(a, 0) + 1

        # Category breakdown
        categories: dict[str, int] = {}
        for r in records:
            c = r.get("category", "unknown")
            categories[c] = categories.get(c, 0) + 1

        # Daily counts
        daily: dict[str, int] = {}
        for r in records:
            day = r.get("timestamp", "")[:10]
            daily[day] = daily.get(day, 0) + 1

        # Unique sessions
        sessions = len({r.get("session_id") for r in records if r.get("session_id")})

        # Busiest day
        busiest_day = max(daily, key=daily.get) if daily else None

        # No-context cancel rate (UX auditor insight)
        canceled = [r for r in records if r.get("action") == "canceled"]
        vague_canceled = [r for r in canceled if r.get("category") == "vague-capture"]
        no_context_cancel_rate = (
            len(vague_canceled) / len(canceled) if canceled else 0.0
        )

        return {
            "total": len(records),
            "actions": actions,
            "categories": categories,
            "daily_counts": daily,
            "sessions": sessions,
            "avg_per_day": round(len(records) / max(len(daily), 1), 1),
            "busiest_day": busiest_day,
            "no_context_cancel_rate": round(no_context_cancel_rate, 2),
        }

    def get_trends(self, weeks: int = 4) -> list[dict]:
        """Get week-over-week trend data.

        Returns list of dicts: [{week_start, total, actions, categories}, ...]
        """
        all_records = self.get_records(days=0)  # All records
        if not all_records:
            return []

        today = date.today()
        trends = []

        for i in range(weeks):
            week_end = today - timedelta(weeks=i)
            week_start = week_end - timedelta(days=6)

            start_str = week_start.isoformat()
            end_str = (week_end + timedelta(days=1)).isoformat()

            week_records = [
                r
                for r in all_records
                if start_str <= r.get("timestamp", "")[:10] <= end_str
            ]

            actions: dict[str, int] = {}
            categories: dict[str, int] = {}
            for r in week_records:
                a = r.get("action", "unknown")
                actions[a] = actions.get(a, 0) + 1
                c = r.get("category", "unknown")
                categories[c] = categories.get(c, 0) + 1

            trends.append(
                {
                    "week_start": start_str,
                    "total": len(week_records),
                    "actions": actions,
                    "categories": categories,
                }
            )

        return trends

    def purge(self, before_date: Optional[str] = None, task_id: Optional[str] = None):
        """Delete records matching criteria. If no criteria, deletes all.

        Args:
            before_date: Delete records before this ISO date
            task_id: Delete records for this specific task
        """
        with self._lock:
            records = self._load()
            original_count = len(records)

            if task_id:
                records = [r for r in records if r.get("task_id") != task_id]
            elif before_date:
                records = [r for r in records if r.get("timestamp", "") >= before_date]
            else:
                records = []

            self._save(records)
            return original_count - len(records)

    def _load(self) -> list[dict]:
        """Load records from JSON file."""
        if not self._file.exists():
            return []
        try:
            with open(self._file) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            logger.debug("Failed to load triage history (non-critical)")
            return []

    def _save(self, records: list[dict]) -> None:
        """Save records to JSON file with restrictive permissions."""
        try:
            # Ensure directory exists with 0700
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.parent.chmod(stat.S_IRWXU)

            # Atomic write: write to temp file, then rename
            tmp_file = self._file.with_suffix(".tmp")
            with open(tmp_file, "w") as f:
                json.dump(records, f, indent=2)

            # Set restrictive permissions before renaming
            tmp_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
            tmp_file.rename(self._file)

        except OSError:
            logger.debug("Failed to save triage history (non-critical)")


# Global singleton instance
triage_tracker = TriageTracker()
