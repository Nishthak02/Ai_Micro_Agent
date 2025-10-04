import os
from dotenv import load_dotenv
from .db import get_conn
from .tools import messaging
import json, logging

logger = logging.getLogger("ai_agent")

# Load .env here too
load_dotenv()
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def run_task(task_id: int, chat_id: str = None):
    """
    Executes stored task from DB and sends to Telegram.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT params_json, enabled FROM task WHERE id=?", (task_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        logger.error(f"Task {task_id} not found.")
        return

    params_json, enabled = row
    if not enabled:
        return

    try:
        plan = json.loads(params_json)
        calls = plan.get("calls", [])
        for c in calls:
            tool = c.get("tool")
            args = c.get("args", {})
            if tool == "messaging.send_message":
                text = args.get("text", "(no text)")
                to_chat = args.get("chat_id") or chat_id or DEFAULT_CHAT_ID
                print(f"🧩 Sending task {task_id} → chat_id={to_chat!r}")
                messaging.send_message(to_chat, text)
            else:
                logger.warning(f"Unknown tool '{tool}' for task {task_id}")
    except Exception as e:
        logger.error(f"Error running task {task_id}: {e}")
