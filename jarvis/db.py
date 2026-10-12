"""SQLite storage: tasks, activity log and settings. One short-lived connection per call,
so the bot, the scheduler and worker threads never share a connection."""
import os
import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("JARVIS_DB", "jarvis.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT,
    due_date TEXT,              -- YYYY-MM-DD or NULL
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("TIMEZONE", "Australia/Melbourne"))


def now() -> datetime:
    return datetime.now(tz())


def today() -> date:
    return now().date()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init(path: str | None = None) -> None:
    global DB_PATH
    if path:
        DB_PATH = path
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _query(sql: str, params=()) -> list[dict]:
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def _execute(sql: str, params=()) -> int:
    with _connect() as conn:
        return conn.execute(sql, params).lastrowid


# settings

def get_setting(key: str) -> str | None:
    rows = _query("SELECT value FROM settings WHERE key = ?", (key,))
    return rows[0]["value"] if rows else None


def set_setting(key: str, value: str) -> None:
    _execute("INSERT INTO settings (key, value) VALUES (?, ?) "
             "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# activity log

def log(kind: str, summary: str) -> None:
    _execute("INSERT INTO activity_log (timestamp, kind, summary) VALUES (?, ?, ?)",
             (now().isoformat(timespec="seconds"), kind, summary[:1000]))


def activity_since(since: datetime, limit: int = 200) -> list[dict]:
    return _query("SELECT * FROM activity_log WHERE timestamp >= ? ORDER BY id DESC LIMIT ?",
                  (since.isoformat(timespec="seconds"), limit))


def recent_activity(limit: int = 50) -> list[dict]:
    return _query("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))


# tasks

def get_task(task_id: int) -> dict | None:
    rows = _query("SELECT * FROM tasks WHERE id = ?", (task_id,))
    return rows[0] if rows else None


def add_task(title: str, notes: str | None = None, due_date: str | None = None) -> dict:
    task_id = _execute("INSERT INTO tasks (title, notes, due_date, status, created_at) "
                       "VALUES (?, ?, ?, 'open', ?)",
                       (title, notes, due_date, now().isoformat(timespec="seconds")))
    return get_task(task_id)


def list_tasks(status: str = "open") -> list[dict]:
    """status: 'open', 'done' or 'all'. Open tasks with a due date come first."""
    where = "" if status == "all" else "WHERE status = ?"
    params = () if status == "all" else (status,)
    return _query(f"SELECT * FROM tasks {where} "
                  "ORDER BY status, due_date IS NULL, due_date, id", params)


def update_task(task_id: int, **fields) -> dict | None:
    """Update any of title, notes, due_date, status. A field set to '' is cleared (notes/due_date)."""
    allowed = {k: v for k, v in fields.items()
               if k in ("title", "notes", "due_date", "status") and v is not None}
    if not get_task(task_id):
        return None
    if "status" in allowed:
        allowed["completed_at"] = now().isoformat(timespec="seconds") if allowed["status"] == "done" else None
    for key in ("notes", "due_date"):
        if allowed.get(key) == "":
            allowed[key] = None
    if allowed:
        sets = ", ".join(f"{k} = ?" for k in allowed)
        _execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*allowed.values(), task_id))
    return get_task(task_id)


def complete_task(task_id: int) -> dict | None:
    return update_task(task_id, status="done")


def due_tasks(on: date | None = None) -> tuple[list[dict], list[dict]]:
    """(overdue, due_today) open tasks."""
    day = (on or today()).isoformat()
    overdue = _query("SELECT * FROM tasks WHERE status = 'open' AND due_date < ? ORDER BY due_date", (day,))
    due_today = _query("SELECT * FROM tasks WHERE status = 'open' AND due_date = ? ORDER BY id", (day,))
    return overdue, due_today
