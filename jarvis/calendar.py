"""Read-only Google Calendar helpers. (Imported as jarvis.calendar, so it doesn't shadow stdlib.)"""
from datetime import datetime, time, timedelta

from jarvis import db
from jarvis.google_auth import service


def get_events(days: int = 1) -> list[dict]:
    """Events from the start of today for `days` days, primary calendar, in local time."""
    tz = db.tz()
    start = datetime.combine(db.today(), time.min, tzinfo=tz)
    end = start + timedelta(days=days)
    resp = service("calendar", "v3").events().list(
        calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=100).execute()
    events = []
    for e in resp.get("items", []):
        if e.get("status") == "cancelled":
            continue
        all_day = "date" in e["start"]
        if all_day:
            s = datetime.fromisoformat(e["start"]["date"]).replace(tzinfo=tz)
            f = datetime.fromisoformat(e["end"]["date"]).replace(tzinfo=tz)
        else:
            s = datetime.fromisoformat(e["start"]["dateTime"]).astimezone(tz)
            f = datetime.fromisoformat(e["end"]["dateTime"]).astimezone(tz)
        events.append({"summary": e.get("summary", "(no title)"), "start": s, "end": f,
                       "all_day": all_day, "location": e.get("location", "")})
    return events


def analyse(events: list[dict], min_gap_minutes: int = 30) -> tuple[list[tuple], list[tuple]]:
    """Return (clashes, gaps) among timed events. clashes: (a, b) pairs that overlap.
    gaps: (start, end) free windows of at least min_gap_minutes between consecutive events."""
    timed = sorted((e for e in events if not e["all_day"]), key=lambda e: e["start"])
    clashes, gaps = [], []
    for i, a in enumerate(timed):
        for b in timed[i + 1:]:
            if b["start"] >= a["end"]:
                break
            clashes.append((a, b))
    latest_end = None
    for e in timed:
        if latest_end and (e["start"] - latest_end) >= timedelta(minutes=min_gap_minutes):
            gaps.append((latest_end, e["start"]))
        latest_end = max(latest_end, e["end"]) if latest_end else e["end"]
    return clashes, gaps
