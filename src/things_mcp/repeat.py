"""Server-side repeating to-dos (CDI-2076).

Things 3 has no supported way to create or edit a repeat rule: the URL scheme,
the AppleScript dictionary and the Shortcuts actions all lack one. So the server
carries the rule itself:

- The rule is a visible ``🔁 repeat:`` line in the to-do's notes. The URL-scheme
  write path returns no UUID, so the notes are how a new to-do carries its rule,
  and copying the notes forward keeps the series going.
- A periodic sweep reads completed to-dos with that line from the logbook (so a
  completion in the Things app counts too) and creates the next occurrence
  through the normal URL-scheme write path.
- ``~/.things-mcp/repeat_state.json`` records every handled completion, keyed by
  its Things UUID, so each completion spawns exactly one occurrence across
  sweeps and restarts.

Canceling or deleting an occurrence ends the series; so does deleting the line.
"""

from __future__ import annotations

import calendar
import json
import re
import stat
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple, Optional

from .logging_config import get_logger

logger = get_logger(__name__)

STATE_FILE = Path.home() / ".things-mcp" / "repeat_state.json"
# ponytail: fixed 10-minute poll, so the next occurrence appears up to ~10 min
# after a completion. Hook complete-task too if that lag ever matters.
SWEEP_SECONDS = 600

MARKER = "🔁 repeat:"
_MARKER_RE = re.compile(
    rf"^{re.escape(MARKER)} (\S+(?: (?:fixed|after-completion))?)", re.MULTILINE
)
_MARKER_LINE_RE = re.compile(rf"^{re.escape(MARKER)}.*(?:\n|$)", re.MULTILINE)

_DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_NTH = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "last": -1}
_ALIASES = {
    "daily": "every:1d",
    "weekly": "every:1w",
    "monthly": "every:1m",
    "yearly": "every:1y",
}
GRAMMAR = (
    "daily | weekly:mon[,thu] | monthly:15 | monthly:last | monthly:2nd-saturday | "
    "monthly:last-friday | every:14d | every:2w | every:3m | every:1y, optionally "
    'followed by " fixed" (default: next date from the schedule) or '
    '" after-completion" (next date from the completion day)'
)


class Rule(NamedTuple):
    spec: str  # canonical rule, e.g. "monthly:2nd-saturday"
    mode: str  # "fixed" | "after-completion"
    kind: str  # "every" | "weekly" | "monthday" | "nth"
    n: int  # interval, day of month, or nth weekday (-1 = last)
    unit: str  # d/w/m/y for "every"
    days: tuple[int, ...]  # weekdays, Monday = 0

    @property
    def text(self) -> str:
        return f"{self.spec} {self.mode}"


def _weekday(name: str) -> int:
    for i, full in enumerate(_DAY_NAMES):
        if len(name) >= 3 and full.startswith(name):
            return i
    raise ValueError(name)


def parse_rule(text: str) -> Rule:
    """Parse a repeat rule; raises ValueError naming the grammar."""
    words = (text or "").strip().lower().split()
    mode = "fixed"
    if len(words) == 2 and words[1] in ("fixed", "after-completion"):
        mode = words.pop()
    try:
        if len(words) != 1:
            raise ValueError(text)
        spec = _ALIASES.get(words[0], words[0])
        kind, _, arg = spec.partition(":")
        if kind == "every":
            m = re.fullmatch(r"([1-9]\d{0,2})([dwmy])", arg)
            return Rule(spec, mode, "every", int(m[1]), m[2], ())
        if kind == "weekly":
            days = tuple(sorted({_weekday(d) for d in arg.split(",")}))
            return Rule(spec, mode, "weekly", 0, "", days)
        if kind == "monthly":
            nth, _, day = arg.partition("-")
            if day:
                return Rule(spec, mode, "nth", _NTH[nth], "", (_weekday(day),))
            n = -1 if arg == "last" else int(arg)
            if n != -1 and not 1 <= n <= 31:
                raise ValueError(arg)
            return Rule(spec, mode, "monthday", n, "", ())
        raise ValueError(kind)
    except (ValueError, KeyError, TypeError):
        raise ValueError(f"Invalid repeat rule {text!r}. Use: {GRAMMAR}.") from None


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _in_month(rule: Rule, y: int, m: int) -> Optional[date]:
    last = calendar.monthrange(y, m)[1]
    if rule.kind == "monthday":
        return date(y, m, last if rule.n == -1 else min(rule.n, last))
    wd = rule.days[0]
    if rule.n == -1:
        d = date(y, m, last)
        return d - timedelta(days=(d.weekday() - wd) % 7)
    first = date(y, m, 1)
    d = first + timedelta(days=(wd - first.weekday()) % 7 + 7 * (rule.n - 1))
    return d if d.month == m else None  # no 5th <weekday> this month


def next_date(rule: Rule, after: date) -> date:
    """First date matching ``rule`` strictly after ``after``."""
    if rule.kind == "every":
        if rule.unit in "dw":
            return after + timedelta(days=rule.n * (7 if rule.unit == "w" else 1))
        # ponytail: day clamps and then drifts (Jan 31 -> Feb 28 -> Mar 28);
        # use monthly:<day> / monthly:last for a fixed day of the month.
        return _add_months(after, rule.n * (12 if rule.unit == "y" else 1))
    if rule.kind == "weekly":
        return next(
            after + timedelta(days=i)
            for i in range(1, 8)
            if (after + timedelta(days=i)).weekday() in rule.days
        )
    y, m = after.year, after.month
    while True:  # a 5th weekday turns up within a few months
        d = _in_month(rule, y, m)
        if d and d > after:
            return d
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


# -- notes marker -------------------------------------------------------------


def rule_in(notes: Optional[str]) -> Optional[Rule]:
    """The server-side rule carried in ``notes``, if any."""
    m = _MARKER_RE.search(notes or "")
    if not m:
        return None
    try:
        return parse_rule(m[1])
    except ValueError:
        return None


def with_rule(notes: Optional[str], rule: Optional[Rule]) -> str:
    """``notes`` with its repeat line replaced by ``rule`` (or removed)."""
    base = _MARKER_LINE_RE.sub("", notes or "").rstrip()
    if rule is None:
        return base
    line = (
        f"{MARKER} {rule.text} (server-side repeat by mcp-things; "
        "delete this line to stop)"
    )
    return f"{base}\n\n{line}" if base else line


# -- next occurrence ----------------------------------------------------------


def _day(value: Any) -> Optional[date]:
    return date.fromisoformat(str(value)[:10]) if value else None


def plan_next(row: dict[str, Any], rule: Rule) -> dict[str, Any]:
    """``add_todo`` kwargs for the occurrence after the completed ``row``.

    The deadline keeps its offset from the start date; title, notes (with the
    repeat line), tags, checklist titles, project/area and heading carry over.
    """
    done = _day(row.get("stop_date")) or date.today()
    start, due = _day(row.get("start_date")), _day(row.get("deadline"))
    base = done if rule.mode == "after-completion" else (start or due or done)
    nxt = next_date(rule, base)
    while nxt < done:  # completed late: skip occurrences already in the past
        nxt = next_date(rule, nxt)

    if start or not due:
        when = nxt.isoformat()
        if row.get("reminder_time"):
            when += f"@{row['reminder_time']}"
        deadline = (nxt + (due - start)).isoformat() if start and due else None
    else:  # deadline-only to-do: the rule drives the deadline
        when = {"Anytime": "anytime", "Someday": "someday"}.get(row.get("start"))
        deadline = nxt.isoformat()

    checklist = [c.get("title") for c in row.get("checklist") or [] if c.get("title")]
    return {
        "title": row.get("title", ""),
        "notes": row.get("notes"),
        "when": when,
        "deadline": deadline,
        "tags": list(row.get("tags") or []) or None,
        "checklist_items": checklist or None,
        "list_id": row.get("project") or row.get("area"),
        "heading": row.get("heading_title"),
    }


# -- state + sweep ------------------------------------------------------------

_lock = threading.Lock()


def _load(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("Repeat state unreadable; re-baselining without spawning")
        return None


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)


def sweep(state_file: Path = STATE_FILE) -> list[dict[str, Any]]:
    """Create the next occurrence for every newly completed repeating to-do.

    Returns the ``add_todo`` kwargs of each occurrence created.
    """
    from . import reader as db
    from .cache import invalidate_caches_for
    from .url_scheme import add_todo, execute_url

    with _lock:
        rows = db.logbook_with_notes(MARKER)
        state = _load(state_file)
        if state is None:
            # First run or lost state: adopt today's logbook without spawning,
            # so a missing file never replays old completions as duplicates.
            # ponytail: a completion made while the state was lost is skipped.
            _save(state_file, {r["uuid"]: {"baseline": True} for r in rows})
            return []

        created = []
        for row in rows:
            uid = row["uuid"]
            if uid in state:
                continue
            rule = rule_in(row.get("notes"))
            if rule is None:
                state[uid] = {"error": "unparseable repeat line"}
                _save(state_file, state)
                continue
            if row.get("heading") and not row.get("project"):
                heading = db.get(row["heading"]) or {}
                row = {**row, "project": heading.get("project")}
            nxt = plan_next(row, rule)
            state[uid] = {
                "rule": rule.text,
                "when": nxt["when"],
                "deadline": nxt["deadline"],
                "at": datetime.now().isoformat(timespec="seconds"),
            }
            # Mark first: a crash right after this loses one occurrence instead
            # of re-creating it on every sweep.
            _save(state_file, state)
            if execute_url(add_todo(**nxt)):
                created.append(nxt)
            else:
                del state[uid]  # retry on the next sweep
                _save(state_file, state)

        if created:
            invalidate_caches_for(["get-tasks", "get-today", "get-upcoming"])
            logger.info("Repeat sweep created %d next occurrence(s)", len(created))
        return created


def start_sweeper() -> threading.Thread:
    """Run ``sweep`` now and every SWEEP_SECONDS in a daemon thread."""

    def loop():
        while True:
            try:
                sweep()
            except Exception:
                logger.error("Repeat sweep failed", exc_info=True)
            time.sleep(SWEEP_SECONDS)

    thread = threading.Thread(target=loop, name="repeat-sweep", daemon=True)
    thread.start()
    return thread
