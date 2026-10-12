"""Entry point: python -m jarvis.main  (Telegram bot + daily briefing scheduler)."""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402

from jarvis import briefing, db, google_auth, telegram_bot  # noqa: E402


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler("jarvis.log")])
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def scheduled_briefing() -> None:
    try:
        await briefing.run(telegram_bot.send_message)
    except Exception as e:
        logging.exception("Scheduled briefing failed")
        db.log("error", f"scheduled briefing: {e}"[:300])


def heartbeat() -> None:
    db.set_setting("bot_heartbeat", db.now().isoformat(timespec="seconds"))


async def post_init(app) -> None:
    scheduler = AsyncIOScheduler(timezone=db.tz())
    scheduler.add_job(scheduled_briefing, briefing.trigger(), id="briefing", misfire_grace_time=3600)
    scheduler.add_job(heartbeat, "interval", minutes=1, id="heartbeat", next_run_time=db.now())
    scheduler.start()
    logging.info("Briefing scheduled; next run %s", scheduler.get_job("briefing").next_run_time)


def main() -> None:
    setup_logging()
    missing = [k for k in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY") if not os.getenv(k)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}. See README.")
    db.init()
    try:
        # Opens a browser the first time; afterwards just loads/refreshes token.json.
        google_auth.get_credentials(interactive=not os.path.exists(google_auth.TOKEN_FILE))
    except Exception as e:
        logging.warning("Google not connected (%s). Tasks still work; email/calendar won't.", e)
        db.log("error", f"startup: Google auth: {e}"[:300])
    if not db.get_setting("owner_chat_id"):
        logging.warning("No owner yet: the FIRST chat to message the bot becomes its owner.")
    db.log("startup", "Jarvis started")
    telegram_bot.create_app(post_init).run_polling()


if __name__ == "__main__":
    main()
