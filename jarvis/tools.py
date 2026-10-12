"""Tool definitions (Anthropic tool-use schema) and their implementations.

Every call is logged to activity_log. Email and calendar content is wrapped in
<untrusted_*> tags because it was written by third parties."""
import json
import logging
from datetime import date

from googleapiclient.errors import HttpError

from jarvis import calendar, db, gmail
from jarvis.google_auth import GoogleAuthError

log = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "add_task",
        "description": "Add a task to the owner's task list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short task title."},
                "notes": {"type": "string", "description": "Optional extra detail."},
                "due_date": {"type": "string", "description": "Optional due date, YYYY-MM-DD."},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List tasks. Defaults to open tasks.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["open", "done", "all"]}},
        },
    },
    {
        "name": "update_task",
        "description": "Change a task's title, notes or due date. Pass an empty string to clear notes or due_date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "notes": {"type": "string"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD, or empty to clear."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as done.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_unread_emails",
        "description": "Unread Gmail inbox messages from the last 24 hours: sender, subject, snippet. Read-only.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_calendar",
        "description": "Google Calendar events from the start of today for N days (1 = today only). Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 14}},
        },
    },
]


class ToolError(Exception):
    """Bad input from the model; message is returned to it so it can correct itself."""


def untrusted(tag: str, text: str) -> str:
    # Neutralise any attempt to close our tag from inside the content.
    safe = text.replace("<untrusted", "&lt;untrusted").replace("</untrusted", "&lt;/untrusted")
    return f"<{tag}>\n{safe}\n</{tag}>"


def format_email(m: dict) -> str:
    return untrusted("untrusted_email",
                     f"From: {m['sender']}\nSubject: {m['subject']}\nReceived: {m['date']}\nSnippet: {m['snippet']}")


def format_event(e: dict) -> str:
    when = (f"{e['start']:%a %d %b} (all day)" if e["all_day"]
            else f"{e['start']:%a %d %b %H:%M}-{e['end']:%H:%M}")
    where = f" @ {e['location']}" if e["location"] else ""
    return untrusted("untrusted_calendar", f"{when}: {e['summary']}{where}")


def _due(value: str | None) -> str | None:
    if not value:
        return value
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ToolError(f"due_date must be YYYY-MM-DD, got {value!r}")


def _task_line(t: dict) -> str:
    due = f" (due {t['due_date']})" if t["due_date"] else ""
    notes = f" - {t['notes']}" if t["notes"] else ""
    return f"#{t['id']} [{t['status']}] {t['title']}{due}{notes}"


def _run(name: str, args: dict) -> str:
    if name == "add_task":
        title = (args.get("title") or "").strip()
        if not title:
            raise ToolError("title is required")
        t = db.add_task(title, args.get("notes") or None, _due(args.get("due_date")))
        return "Added " + _task_line(t)
    if name == "list_tasks":
        status = args.get("status", "open")
        if status not in ("open", "done", "all"):
            raise ToolError("status must be open, done or all")
        tasks = db.list_tasks(status)
        return "\n".join(map(_task_line, tasks)) or f"No {status} tasks."
    if name == "update_task":
        t = db.update_task(int(args["id"]), title=args.get("title"), notes=args.get("notes"),
                           due_date=_due(args.get("due_date")))
        return "Updated " + _task_line(t) if t else f"No task #{args['id']}."
    if name == "complete_task":
        t = db.complete_task(int(args["id"]))
        return "Completed " + _task_line(t) if t else f"No task #{args['id']}."
    if name == "get_unread_emails":
        mails = gmail.get_unread()
        return "\n".join(map(format_email, mails)) or "No unread email in the last 24 hours."
    if name == "get_calendar":
        days = max(1, min(int(args.get("days", 1)), 14))
        events = calendar.get_events(days)
        clashes, _ = calendar.analyse(events)
        out = "\n".join(map(format_event, events)) or "No events."
        if clashes:
            out += "\nClashes: " + "; ".join(f"{a['summary']!r} overlaps {b['summary']!r}" for a, b in clashes)
        return out
    raise ToolError(f"Unknown tool {name}")


def run(name: str, args: dict) -> str:
    """Execute a tool. Never raises: errors come back as text for the model to relay."""
    try:
        result = _run(name, args or {})
        db.log("tool", f"{name} {json.dumps(args, ensure_ascii=False)}"[:300])
        return result
    except ToolError as e:
        db.log("tool_error", f"{name}: {e}")
        return f"Error: {e}"
    except GoogleAuthError as e:
        db.log("error", f"{name}: Google auth: {e}")
        return f"Error: {e}"
    except HttpError as e:
        log.exception("Google API error in %s", name)
        db.log("error", f"{name}: Google API {e.status_code}")
        return f"Error: Google returned {e.status_code}. Try again shortly."
    except Exception as e:
        log.exception("Tool %s failed", name)
        db.log("error", f"{name}: {type(e).__name__}: {e}")
        return f"Error: {name} failed ({type(e).__name__})."
