# src/orchestrator.py
import json
import traceback
from datetime import datetime
from src.mcp import run_call
from src.db import get_conn


def log_event(event_type: str, message: str):
    """
    Logs events and errors to the database for debugging and traceability.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                message TEXT,
                timestamp TEXT
            )
            """
        )
        conn.commit()
        cur.execute(
            "INSERT INTO system_logs (event_type, message, timestamp) VALUES (?, ?, ?)",
            (event_type, message, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Log insert failed: {e}")


def run_task(task_row):
    """
    Executes a saved task from the DB via MCP.
    Each task_row should have 'params_json' with calls[].
    """
    try:
        params_json = task_row.get("params_json")
        if isinstance(params_json, str):
            params = json.loads(params_json)
        else:
            params = params_json

        calls = params.get("calls", [])
        for call in calls:
            print(f"⚙️ Orchestrator dispatching MCP call: {call}")
            run_call(call)  # 🔥 The MCP executes the tool dynamically
        return True
    except Exception as e:
        print(f"❌ run_task failed: {e}")
        return False

    except Exception as e:
        print(f"⚠️ Orchestrator critical error: {e}")
        print(traceback.format_exc())
        log_event("FATAL", f"Critical orchestrator failure: {e}")
        return False


def run_task_from_db(task_id: int):
    """
    Utility to run a task directly from the database (used by scheduler or manual trigger).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT params_json FROM task WHERE id=?", (task_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            print(f"⚠️ Task ID {task_id} not found in DB.")
            return False

        params_json = row[0]
        try:
            task_plan = json.loads(params_json)
        except json.JSONDecodeError:
            print(f"⚠️ Task {task_id} has invalid JSON structure.")
            return False

        print(f"🗂 Running task from DB: ID={task_id}")
        return run_task(task_plan)

    except Exception as e:
        print(f"⚠️ run_task_from_db error: {e}")
        log_event("ERROR", f"run_task_from_db failed for task {task_id}: {e}")
        return False
