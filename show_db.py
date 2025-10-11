from src.db import get_conn

conn = get_conn()
cur = conn.cursor()

print("\n🧾 Available Tables:")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print("-", row[0])

print("\n👥 Users:")
for row in cur.execute("SELECT * FROM user_registry;"):
    print(row)

print("\n🕒 Tasks:")
for row in cur.execute("SELECT id, type, schedule_rule FROM task;"):
    print(row)

conn.close()
