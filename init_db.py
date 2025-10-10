# init_db.py
import sqlite3
import os

# Ensure migrations folder exists
os.makedirs("migrations", exist_ok=True)
os.makedirs("src", exist_ok=True)

# Path to database file
db_path = os.path.join("src", "ai_agent.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Run schema
cur.executescript("""
CREATE TABLE IF NOT EXISTS "user" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    chat_id TEXT UNIQUE,
    timezone TEXT
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    params_json TEXT,
    schedule_rule TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    started_at TEXT,
    ended_at TEXT,
    ok INTEGER,
    outputs_json TEXT,
    error_text TEXT,
    attempt INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT UNIQUE,
    name TEXT,
    username TEXT,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS order_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_chat_id TEXT,
    store_chat_id TEXT,
    store_name TEXT,
    item TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS order_chat_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    buyer_chat_id TEXT,
    store_chat_id TEXT,
    active INTEGER DEFAULT 1
);
""")

conn.commit()
conn.close()
print(f"✅ Fresh ai_agent.db created at: {db_path}")
