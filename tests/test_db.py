from datetime import date, timedelta

from jarvis import db


def test_settings_roundtrip():
    assert db.get_setting("owner_chat_id") is None
    db.set_setting("owner_chat_id", "42")
    db.set_setting("owner_chat_id", "43")
    assert db.get_setting("owner_chat_id") == "43"


def test_task_lifecycle():
    t = db.add_task("Buy milk", due_date="2030-01-01")
    assert t["status"] == "open" and t["completed_at"] is None
    assert [x["id"] for x in db.list_tasks()] == [t["id"]]
    done = db.complete_task(t["id"])
    assert done["status"] == "done" and done["completed_at"]
    assert db.list_tasks("open") == []
    assert len(db.list_tasks("all")) == 1


def test_update_clears_due_date_and_ignores_unknown_fields():
    t = db.add_task("x", notes="n", due_date="2030-01-01")
    t = db.update_task(t["id"], due_date="", notes=None, bogus="y")
    assert t["due_date"] is None and t["notes"] == "n"
    assert db.update_task(999, title="nope") is None


def test_due_tasks_splits_overdue_and_today():
    today = date(2030, 5, 10)
    db.add_task("late", due_date=(today - timedelta(days=1)).isoformat())
    db.add_task("now", due_date=today.isoformat())
    db.add_task("later", due_date=(today + timedelta(days=1)).isoformat())
    db.add_task("whenever")
    overdue, due_today = db.due_tasks(today)
    assert [t["title"] for t in overdue] == ["late"]
    assert [t["title"] for t in due_today] == ["now"]


def test_activity_log():
    db.log("tool", "did a thing")
    rows = db.recent_activity()
    assert rows[0]["kind"] == "tool" and rows[0]["summary"] == "did a thing"
