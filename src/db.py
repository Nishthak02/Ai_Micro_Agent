import sqlite3
from contextlib import closing
from pathlib import Path
from .config import DATABASE_URL
import json

DB_FILE = DATABASE_URL.replace('sqlite:///', '')

def init_db():
    schema_file = Path(__file__).parent / "schema.sql"  # <-- define schema_file path
    if not Path(DB_FILE).exists():
        conn = sqlite3.connect(DB_FILE)
        with closing(conn):
            cur = conn.cursor()
            with open(schema_file, "r", encoding="utf-8") as f:
                cur.executescript(f.read())
            conn.commit()

def get_conn():
    print(f"📂 Connecting to DB file: {DB_FILE}")  # <-- add this line
    return sqlite3.connect(DB_FILE)


def create_user(name: str, chat_id: str, timezone: str = "Asia/Kolkata"):
    """Create a new user."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user (name, chat_id, timezone) VALUES (?, ?, ?)",
        (name, chat_id, timezone)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def create_task(user_id: int, task_type: str, plan: dict, schedule_rule: str = "*", enabled: int = 1):
    """Create a new task linked to a user."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO task (user_id, type, params_json, schedule_rule, enabled) VALUES (?, ?, ?, ?, ?)",
        (user_id, task_type, json.dumps(plan), schedule_rule, enabled)
    )


    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def list_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, task_type, params_json, schedule_rule, enabled FROM task")
    rows = cur.fetchall()
    conn.close()
    return rows

# Auto initialize database if missing
init_db()
