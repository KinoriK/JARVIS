"""Telegram transport. The only module that knows about Telegram.

Interface used elsewhere: create_app(), send_message(text)."""
import logging
import os
from datetime import datetime, time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from jarvis import brain, briefing, db

log = logging.getLogger(__name__)
_app: Application | None = None
MAX_LEN = 4000  # Telegram's limit is 4096

HELP = """At your service. Commands:
/tasks - open tasks
/briefing - this morning's briefing, now
/today - what I've done today
/help - this message
Anything else, just say it."""


async def send_message(text: str) -> None:
    """Send text to the owner. No-op (with a warning) until someone has claimed the bot."""
    owner = db.get_setting("owner_chat_id")
    if not owner:
        log.warning("No owner yet; dropping message: %s", text[:80])
        return
    for i in range(0, len(text), MAX_LEN):
        await _app.bot.send_message(chat_id=int(owner), text=text[i:i + MAX_LEN])


def _is_owner(update: Update) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    owner = db.get_setting("owner_chat_id")
    if owner is None:
        db.set_setting("owner_chat_id", str(chat.id))
        db.log("owner", f"Owner set to chat {chat.id}")
        log.warning("OWNER LOCK: chat %s (%s) is now the owner. Delete owner_chat_id from settings to reset.",
                    chat.id, chat.username or chat.full_name)
        return True
    return str(chat.id) == owner


def owner_only(handler):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _is_owner(update):
            return  # silence for strangers
        try:
            await handler(update, context)
        except Exception as e:
            log.exception("Handler %s failed", handler.__name__)
            db.log("error", f"telegram {handler.__name__}: {type(e).__name__}: {e}"[:300])
            await update.effective_chat.send_message("Something went wrong there. It's been logged.")
    return wrapped


async def _reply(update: Update, text: str) -> None:
    for i in range(0, len(text), MAX_LEN):
        await update.effective_chat.send_message(text[i:i + MAX_LEN])


@owner_only
async def cmd_start(update, context):
    await _reply(update, "Good day. Jarvis, at your service.\n\n" + HELP)


@owner_only
async def cmd_help(update, context):
    await _reply(update, HELP)


@owner_only
async def cmd_tasks(update, context):
    tasks = db.list_tasks("open")
    if not tasks:
        return await _reply(update, "No open tasks. Enviable.")
    lines = [f"#{t['id']} {t['title']}" + (f" (due {t['due_date']})" if t["due_date"] else "") for t in tasks]
    await _reply(update, "Open tasks:\n" + "\n".join(lines))


@owner_only
async def cmd_briefing(update, context):
    await update.effective_chat.send_action(ChatAction.TYPING)
    await _reply(update, await briefing.run())


@owner_only
async def cmd_today(update, context):
    midnight = datetime.combine(db.today(), time.min, tzinfo=db.tz())
    rows = db.activity_since(midnight)
    if not rows:
        return await _reply(update, "Nothing yet today.")
    lines = [f"{r['timestamp'][11:16]} {r['kind']}: {r['summary']}" for r in reversed(rows)]
    await _reply(update, "Today:\n" + "\n".join(lines))


@owner_only
async def on_text(update, context):
    await update.effective_chat.send_action(ChatAction.TYPING)
    await _reply(update, await brain.reply(update.message.text))


def create_app(post_init=None) -> Application:
    global _app
    # Generous timeouts: the defaults (5s) give up too fast on slow or filtered connections.
    builder = (Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"])
               .connect_timeout(20).read_timeout(30))
    if post_init:
        builder = builder.post_init(post_init)
    _app = builder.build()
    for name, fn in [("start", cmd_start), ("help", cmd_help), ("tasks", cmd_tasks),
                     ("briefing", cmd_briefing), ("today", cmd_today)]:
        _app.add_handler(CommandHandler(name, fn))
    _app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return _app
