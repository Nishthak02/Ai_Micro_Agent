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