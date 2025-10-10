import os
import json
import base64
import datetime
from email import message_from_bytes
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from src.tools.messaging import send_message

# ───────────────────────────────
# CONFIG
# ───────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKENS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tokens"))
os.makedirs(TOKENS_DIR, exist_ok=True)

# ───────────────────────────────
# TOKEN MANAGEMENT
# ───────────────────────────────
def get_user_token_path(chat_id: str):
    """Return token file path for a specific user."""
    path = os.path.join(TOKENS_DIR, f"token_{chat_id}.json")
    print(f"🔍 Looking for token at: {path}")
    return path


def load_credentials(chat_id: str):
    """Load and refresh Gmail OAuth credentials."""
    token_path = get_user_token_path(chat_id)
    creds = None

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print(f"🧩 Loaded creds: valid={creds.valid}, expired={creds.expired}, has_refresh={creds.refresh_token is not None}")
        except Exception as e:
            print(f"⚠️ Failed to load creds from {token_path}: {e}")
            creds = None

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            print("🔄 Token refreshed successfully")
        except Exception as e:
            print("❌ Token refresh failed:", e)
            creds = None

    return creds


# ───────────────────────────────
# FETCH EMAILS (Improved)
# ───────────────────────────────
def fetch_recent_emails(creds, max_results=5):
    """Fetch recent unread emails with sender, subject, and snippet."""
    service = build("gmail", "v1", credentials=creds)
    results = service.users().messages().list(
        userId="me", maxResults=max_results, labelIds=["INBOX"]
    ).execute()

    messages = results.get("messages", [])
    summaries = []

    for msg in messages:
        m = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        headers = m.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(no subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "(unknown sender)")
        snippet = m.get("snippet", "").strip()

        # Try to decode the message body for richer preview
        body = ""
        parts = m.get("payload", {}).get("parts", [])
        for part in parts:
            data = part.get("body", {}).get("data")
            if data:
                try:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    body = " ".join(body.split())[:200]
                    break
                except Exception:
                    pass

        summaries.append({
            "from": sender,
            "subject": subject,
            "snippet": snippet[:100] + "...",
            "body": body or snippet
        })
    return summaries


# ───────────────────────────────
# MAIN SUMMARY FUNCTION (Improved)
# ───────────────────────────────
def send_daily_email_summary(chat_id: str, max_results: int = 5):
    """Generate and send Gmail summary to user."""
    creds = load_credentials(chat_id)
    if not creds:
        send_message(chat_id, "⚠️ Could not fetch email summary: No Gmail token found or token invalid. Please run /link_gmail again.")
        return

    try:
        emails = fetch_recent_emails(creds, max_results=max_results)
        if not emails:
            send_message(chat_id, "📭 No new emails found in your inbox.")
            return

        summary_lines = []
        for e in emails:
            line = (
                f"📧 *From:* {e['from']}\n"
                f"✉️ *Subject:* {e['subject']}\n"
                f"📝 {e['body'][:150]}...\n"
                f"──────────────────────────────"
            )
            summary_lines.append(line)

        summary_text = "📬 *Your Gmail Summary:*\n\n" + "\n\n".join(summary_lines)
        send_message(chat_id, summary_text, parse_mode="Markdown")

    except Exception as e:
        print("❌ Email summary error:", e)
        send_message(chat_id, f"⚠️ Failed to generate email summary: {e}")
