"""Read-only Gmail helpers."""
import html
import time
from email.utils import parseaddr

from jarvis.google_auth import service

AUTOMATED_HINTS = ("noreply", "no-reply", "donotreply", "do-not-reply", "notifications@",
                   "notification@", "newsletter", "mailer-daemon", "bounce")


def get_unread(hours: int = 24, limit: int = 25) -> list[dict]:
    """Unread inbox mail from the last `hours`: id, sender, subject, date, snippet, automated."""
    gmail = service("gmail", "v1")
    after = int(time.time()) - hours * 3600
    resp = gmail.users().messages().list(
        userId="me", q=f"is:unread in:inbox after:{after}", maxResults=limit).execute()
    out = []
    for ref in resp.get("messages", []):
        msg = gmail.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe", "Precedence"]).execute()
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        sender = headers.get("from", "")
        out.append({
            "id": ref["id"],
            "sender": sender,
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "snippet": html.unescape(msg.get("snippet", "")),
            "automated": is_automated(sender, headers),
        })
    return out


def is_automated(sender: str, headers: dict) -> bool:
    addr = parseaddr(sender)[1].lower()
    return (any(h in addr for h in AUTOMATED_HINTS)
            or "list-unsubscribe" in headers
            or headers.get("precedence", "").lower() in ("bulk", "list", "junk"))


def needs_reply(hours: int = 24) -> list[dict]:
    """Unread mail from real people (not newsletters/notifications), newest first."""
    return [m for m in get_unread(hours) if not m["automated"]]
