"""Local dashboard: python -m jarvis.web  -> http://127.0.0.1:8000

Serves the UI and a JSON API. Every /api call needs `Authorization: Bearer $DASHBOARD_TOKEN`.
Binds to 127.0.0.1 only."""
import asyncio
import json
import logging
import os
import secrets
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from jarvis import brain, briefing, calendar, db, gmail, google_auth  # noqa: E402
from jarvis.google_auth import GoogleAuthError  # noqa: E402

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
HOST, PORT = "127.0.0.1", 8000


def require_token(authorization: str = Header(default="")) -> None:
    expected = os.getenv("DASHBOARD_TOKEN", "")
    given = authorization.removeprefix("Bearer ").strip()
    if not expected or not secrets.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "Invalid or missing dashboard token.")


api = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


def google_call(what: str, fn, *args):
    """Run a Google helper, turning failures into a friendly 503 and a log entry."""
    try:
        return fn(*args)
    except GoogleAuthError as e:
        db.log("error", f"dashboard {what}: {e}"[:300])
        raise HTTPException(503, str(e))
    except HttpError as e:
        log.exception("Google %s failed", what)
        db.log("error", f"dashboard {what}: Google API {e.status_code}")
        raise HTTPException(503, f"Google returned {e.status_code}. Try again shortly.")
    except Exception as e:
        log.exception("%s failed", what)
        db.log("error", f"dashboard {what}: {type(e).__name__}: {e}"[:300])
        raise HTTPException(503, f"Couldn't load {what} ({type(e).__name__}).")


# tasks

class NewTask(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    due_date: date | Literal[""] | None = None  # "" clears it
    status: Literal["open", "done"] | None = None


@api.get("/tasks")
def get_tasks(status: Literal["open", "done", "all"] = "open"):
    return db.list_tasks(status)


@api.post("/tasks", status_code=201)
def create_task(body: NewTask):
    t = db.add_task(body.title.strip(), body.notes or None, body.due_date.isoformat() if body.due_date else None)
    db.log("dashboard", f"Added task #{t['id']} {t['title']}")
    return t


@api.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch):
    fields = body.model_dump(exclude_unset=True)
    if isinstance(fields.get("due_date"), date):
        fields["due_date"] = fields["due_date"].isoformat()
    t = db.update_task(task_id, **fields)
    if not t:
        raise HTTPException(404, f"No task #{task_id}.")
    db.log("dashboard", f"Updated task #{task_id}: {', '.join(fields)}")
    return t


# briefing

@api.get("/briefing/latest")
def latest_briefing():
    return {"text": db.get_setting("last_briefing_text"), "at": db.get_setting("last_briefing_at")}


@api.post("/briefing/run")
async def run_briefing():
    text = await briefing.run()
    return {"text": text, "at": db.get_setting("last_briefing_at")}


# google

@api.get("/calendar/today")
def calendar_today():
    events = google_call("calendar", calendar.get_events, 1)
    clashes, gaps = calendar.analyse(events)
    clashing = {id(e) for pair in clashes for e in pair}
    return {
        "events": [{"summary": e["summary"], "start": e["start"].isoformat(), "end": e["end"].isoformat(),
                    "all_day": e["all_day"], "location": e["location"], "clash": id(e) in clashing}
                   for e in events],
        "gaps": [{"start": s.isoformat(), "end": f.isoformat()} for s, f in gaps],
    }


@api.get("/inbox/needs-reply")
def inbox_needs_reply():
    return google_call("inbox", gmail.needs_reply)


# activity / status

@api.get("/activity")
def activity(limit: int = 50):
    return db.recent_activity(max(1, min(limit, 200)))


@api.get("/status")
def status():
    beat = db.get_setting("bot_heartbeat")
    bot_online = bool(beat) and db.now() - datetime.fromisoformat(beat) < timedelta(minutes=3)
    nxt = briefing.next_run()
    return {
        "online": True,
        "bot_online": bot_online,
        "last_heartbeat": beat,
        "last_briefing_at": db.get_setting("last_briefing_at"),
        "next_briefing_at": nxt.isoformat() if nxt else None,
        "google_connected": os.path.exists(google_auth.TOKEN_FILE),
        "owner_set": bool(db.get_setting("owner_chat_id")),
        "open_tasks": len(db.list_tasks("open")),
        "model": brain.model(),
        "timezone": db.tz().key,
        "now": db.now().isoformat(timespec="seconds"),
    }


# chat

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@api.post("/chat")
async def chat(body: ChatIn):
    """Streams NDJSON lines: {"type":"text","delta":...} / {"type":"tool","name":...} / {"type":"done","text":...}."""
    queue: asyncio.Queue = asyncio.Queue()

    async def on_text(delta):
        await queue.put({"type": "text", "delta": delta})

    async def on_tool(name):
        await queue.put({"type": "tool", "name": name})

    async def worker():
        final = await brain.reply(body.message, on_text, on_tool)  # never raises
        await queue.put({"type": "done", "text": final})

    async def stream():
        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item) + "\n"
                if item["type"] == "done":
                    break
        finally:
            await task

    db.log("dashboard", "Chat message")
    return StreamingResponse(stream(), media_type="application/x-ndjson")


app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(api)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler("jarvis.log")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    token = os.getenv("DASHBOARD_TOKEN")
    if not token:
        sys.exit(f"Set DASHBOARD_TOKEN in .env first, e.g.\nDASHBOARD_TOKEN={secrets.token_urlsafe(24)}")
    db.init()
    print(f"\n  Jarvis dashboard: http://{HOST}:{PORT}/#token={token}\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
