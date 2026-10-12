"""Google OAuth: read-only Gmail + Calendar scopes, token cached in token.json.

Run `python -m jarvis.google_auth` to (re-)authorise in a browser."""
import logging
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
REAUTH_HINT = "Google access needs re-authorising: run `python -m jarvis.google_auth` on the machine running Jarvis."

log = logging.getLogger(__name__)


class GoogleAuthError(Exception):
    """Raised when we have no usable token. The message is safe to show the owner."""


def _save(creds: Credentials) -> None:
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)


def get_credentials(interactive: bool = False) -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
            return creds
        except RefreshError as e:
            log.warning("Google token refresh failed: %s", e)
            if not interactive:
                raise GoogleAuthError(REAUTH_HINT) from e
    if not interactive:
        raise GoogleAuthError(REAUTH_HINT)
    if not os.path.exists(CREDENTIALS_FILE):
        raise GoogleAuthError(f"{CREDENTIALS_FILE} not found. See README: 'Google Cloud setup'.")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    _save(creds)
    log.info("Google authorisation saved to %s", TOKEN_FILE)
    return creds


def service(name: str, version: str):
    return build(name, version, credentials=get_credentials(), cache_discovery=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)  # force a fresh consent so scopes are exactly ours
    get_credentials(interactive=True)
    print("Done. token.json saved.")
