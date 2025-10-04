# init_db.py
import sqlite3
import os

# Path to your database file
db_path = os.path.join("src", "ai_agent.db")
os.makedirs("src", exist_ok=True)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create the task table
cur.execute("""
CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT,
    params_json TEXT,
    schedule_rule TEXT,
    enabled INTEGER DEFAULT 1
);
""")

conn.commit()
conn.close()
print("✅ Fresh ai_agent.db created at:", db_path)
