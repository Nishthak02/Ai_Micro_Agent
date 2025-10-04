import imaplib
import email
from ..config import IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD


# Simple read-only unread fetcher - production: better parsing and security


def fetch_unread(limit=20):
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    M.login(IMAP_USER, IMAP_PASSWORD)
    M.select('INBOX')
    typ, data = M.search(None, '(UNSEEN)')
    ids = data[0].split()[-limit:]
    emails = []
    for i in ids:
        typ, msg_data = M.fetch(i, '(RFC822.HEADER)')
        # naive header parse
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        emails.append({'from': msg.get('From'), 'subject': msg.get('Subject')})
        M.logout()
        return emails


# Example summarizer stub - production: call Ollama to summarize


def summarize_unread(chat_id: str, since_days: int=1):
    items = fetch_unread()
    bullets = ['{} - {}'.format(i.get('from'), i.get('subject')) for i in items]
    text = 'Email summary:\n' + '\n'.join(['- ' + b for b in bullets[:6]])
    return {'summary': text}