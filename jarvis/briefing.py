"""Morning briefing: gather calendar, mail and tasks, have Claude write it, send it."""
import asyncio
import logging
import os
from datetime import datetime
from typing import Awaitable, Callable

from apscheduler.triggers.cron import CronTrigger

from jarvis import brain, calendar, db, gmail, tools

log = logging.getLogger(__name__)

INSTRUCTIONS = """Write this morning's briefing from the data below. It will be read on a phone.

Format (plain text, keep it short, skip a section if empty):
- One-line greeting.
- CALENDAR: today's events in time order; flag clashes and note useful free gaps.
- REPLIES: emails that likely need a reply from him, most important first (max 5), one line each.
  Ignore newsletters, receipts and notifications.
- TASKS: overdue first, then due today.
- WATCH: one line on anything risky or urgent, or "Nothing alarming." if so.

If a data source failed, say so in one line and carry on."""


def trigger() -> CronTrigger:
    hour, minute = os.getenv("BRIEFING_TIME", "07:00").split(":")
    return CronTrigger(hour=int(hour), minute=int(minute), timezone=db.tz())


def next_run() -> datetime | None:
    return trigger().get_next_fire_time(None, db.now())


def gather() -> str:
    """Collect the raw material as text. Each source fails independently."""
    parts = [f"Today is {db.now():%A %d %B %Y}."]
    try:
        events = calendar.get_events(1)
        clashes, gaps = calendar.analyse(events)
        parts.append("CALENDAR EVENTS:\n" + ("\n".join(map(tools.format_event, events)) or "None."))
        if clashes:
            parts.append("CLASHES:\n" + "\n".join(f"{a['summary']!r} overlaps {b['summary']!r}" for a, b in clashes))
        if gaps:
            parts.append("FREE GAPS:\n" + "\n".join(f"{s:%H:%M}-{e:%H:%M}" for s, e in gaps))
    except Exception as e:
        log.exception("Briefing: calendar failed")
        db.log("error", f"briefing: calendar: {e}"[:300])
        parts.append(f"CALENDAR: unavailable ({e})")
    try:
        mails = gmail.needs_reply()
        parts.append("UNREAD EMAIL FROM PEOPLE (last 24h):\n" + ("\n".join(map(tools.format_email, mails)) or "None."))
    except Exception as e:
        log.exception("Briefing: gmail failed")
        db.log("error", f"briefing: gmail: {e}"[:300])
        parts.append(f"EMAIL: unavailable ({e})")
    overdue, due_today = db.due_tasks()
    parts.append("OVERDUE TASKS:\n" + ("\n".join(f"#{t['id']} {t['title']} (due {t['due_date']})" for t in overdue) or "None."))
    parts.append("DUE TODAY:\n" + ("\n".join(f"#{t['id']} {t['title']}" for t in due_today) or "None."))
    return "\n\n".join(parts)


async def build() -> str:
    data = await asyncio.to_thread(gather)
    try:
        return await brain.complete(f"{INSTRUCTIONS}\n\n{data}")
    except Exception as e:
        log.exception("Briefing: Claude failed")
        db.log("error", f"briefing: Claude: {e}"[:300])
        return "Good morning. I couldn't compose the briefing (Claude unavailable), so here is the raw list:\n\n" + data


async def run(send: Callable[[str], Awaitable[None]] | None = None) -> str:
    """Build the briefing, store it, and send it via `send` if given."""
    text = await build()
    db.set_setting("last_briefing_at", db.now().isoformat(timespec="seconds"))
    db.set_setting("last_briefing_text", text)
    brain.remember("(Morning briefing, please.)", text)  # so follow-up questions have context
    db.log("briefing", "Morning briefing built" + (" and sent" if send else ""))
    if send:
        await send(text)
    return text
