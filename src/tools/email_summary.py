import os
import json
import datetime
import base64
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from src.tools.messaging import send_message
from src.config import OLLAMA_URL, OLLAMA_MODEL

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), '../../credentials.json')
TOKENS_DIR = os.path.join(os.path.dirname(__file__), '../../tokens')
os.makedirs(TOKENS_DIR, exist_ok=True)


def get_gmail_service(chat_id: str):
    """Authenticate Gmail for a specific Telegram user."""
    token_path = os.path.join(TOKENS_DIR, f'{chat_id}.json')
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def fetch_recent_emails(chat_id: str, limit=5):
    """Fetch recent Gmail messages for the user."""
    service = get_gmail_service(chat_id)
    results = service.users().messages().list(userId='me', maxResults=limit, labelIds=['INBOX']).execute()
    messages = results.get('messages', [])
    emails = []

    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
        headers = {h['name']: h['value'] for h in m['payload']['headers']}
        subject = headers.get('Subject', '(no subject)')
        sender = headers.get('From', '(unknown)')
        snippet = m.get('snippet', '')[:150]
        emails.append(f"📩 *{subject}*\nFrom: {sender}\n→ {snippet}")

    return emails


def summarize_emails_via_ollama(emails):
    """Summarize the given emails using Ollama model."""
    if not emails:
        return "No recent emails found."

    text = "\n\n".join(emails)
    prompt = (
        f"Summarize these emails briefly into key highlights — avoid exact details, "
        f"focus on what topics they cover and any important actions.\n\n{text}"
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt},
            timeout=90
        )
        data = response.json()
        return data.get("response", "No summary available.")
    except Exception as e:
        return f"⚠️ Ollama summarization failed: {e}"


def send_daily_email_summary(chat_id: str):
    """Fetch, summarize, and send email summary for that user."""
    try:
        emails = fetch_recent_emails(chat_id)
        summary = summarize_emails_via_ollama(emails)
        send_message(chat_id, f"📬 *Your Email Summary for Today:*\n\n{summary}")
    except Exception as e:
        send_message(chat_id, f"⚠️ Could not fetch email summary: {e}")


import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from src.tools.messaging import send_message

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../credentials.json"))
TOKENS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tokens"))
os.makedirs(TOKENS_DIR, exist_ok=True)

def start_gmail_oauth(chat_id):
    """Start the Gmail OAuth flow and save token for the user."""
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

        # Generate the consent URL manually and send it to Telegram
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true'
        )

        send_message(chat_id, f"🔗 Please visit this URL to authorize Gmail access:\n{auth_url}")

        # Run the local server silently — suppressing its own URL print
        creds = flow.run_local_server(port=8080, open_browser=False)
        print("✅ OAuth flow completed successfully")

        # Save user token
        token_path = os.path.join(TOKENS_DIR, f"token_{chat_id}.json")
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

        send_message(chat_id, "✅ Gmail account successfully linked! You can now use /emailsummary now or get daily summaries.")
    except Exception as e:
        send_message(chat_id, f"⚠️ Gmail OAuth failed: {e}")
        print("❌ Gmail OAuth error:", e)
