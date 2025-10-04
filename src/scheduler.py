from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging
from src.orchestrator import run_task
from src.db import get_conn
import json

logger = logging.getLogger("ai_agent")
IST = pytz.timezone("Asia/Kolkata")

def parse_rrule_to_kwargs(rrule_str: str):
    """Converts simple RRULE strings into APScheduler arguments."""
    if not rrule_str:
        return {"seconds": 60}  # default: every 1 min

    # Example: RRULE:FREQ=MINUTELY;INTERVAL=5
    parts = {}
    try:
        rule = rrule_str.replace("RRULE:", "")
        for kv in rule.split(";"):
            if "=" in kv:
                key, val = kv.split("=")
                parts[key.strip()] = val.strip()

        freq = parts.get("FREQ", "MINUTELY").upper()
        interval = int(parts.get("INTERVAL", 1))

        if freq == "SECONDLY":
            return {"seconds": interval}
        elif freq == "MINUTELY":
            return {"minutes": interval}
        elif freq == "HOURLY":
            return {"hours": interval}
        elif freq == "DAILY":
            return {"days": interval}
        elif freq == "WEEKLY":
            return {"weeks": interval}
        else:
            return {"minutes": 1}  # fallback default
    except Exception as e:
        logger.error(f"⚠️ Failed to parse RRULE: {e}")
        return {"minutes": 1}

def register_all_tasks(sched):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, schedule_rule FROM task WHERE enabled=1")
    for tid, rule in cur.fetchall():
        try:
            kwargs = parse_rrule_to_kwargs(rule)
            sched.add_job(run_task, "interval", args=[tid], **kwargs)
            print(f"🕒 Registered task {tid} ({kwargs})")
        except Exception as e:
            logger.error(f"⚠️ Could not register task {tid}: {e}")
    conn.close()

def start():
    sched = BackgroundScheduler(timezone=IST)
    register_all_tasks(sched)
    sched.start()
    print("✅ Scheduler started. Press Ctrl+C to exit.")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sched.shutdown()
        print("🛑 Scheduler stopped.")
