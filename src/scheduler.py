# src/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging
from src.orchestrator import run_task
from src.db import get_conn
import json
import re

logger = logging.getLogger("ai_agent")
IST = pytz.timezone("Asia/Kolkata")


def _extract_interval(parts, default=1):
    v = parts.get("INTERVAL")
    try:
        return int(float(v)) if v is not None else default
    except Exception:
        return default


def _int_or_none(val):
    try:
        return int(val)
    except Exception:
        return None


def parse_rrule_to_kwargs(rrule_str: str):
    """
    Converts an RRULE string into either:
      - ('interval', kwargs)  where kwargs are e.g. {"seconds": 5}
      - ('cron', kwargs)      where kwargs can be passed to CronTrigger (hour, minute, day_of_week)
    Returns tuple (trigger_type, kwargs)
    """
    if not rrule_str or not isinstance(rrule_str, str):
        return "interval", {"minutes": 1}  # default

    try:
        rule = rrule_str.upper().replace("RRULE:", "")
        parts = {}
        for kv in rule.split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parts[k.strip()] = v.strip()

        freq = parts.get("FREQ", "MINUTELY").upper()

        # If RRULE specifies BYHOUR/BYMINUTE (time-based), prefer cron trigger for exact times
        if freq in ("DAILY", "WEEKLY"):
            byhour = _int_or_none(parts.get("BYHOUR"))
            byminute = _int_or_none(parts.get("BYMINUTE"))
            byday = parts.get("BYDAY")  # e.g. MO,TU
            cron_kwargs = {}
            if byhour is not None:
                cron_kwargs["hour"] = byhour
            if byminute is not None:
                cron_kwargs["minute"] = byminute
            if byday:
                # APScheduler cron uses day_of_week as mon,tue,... so convert MO -> mon
                # Accept both comma-separated lists and single values
                dow_map = {"MO": "mon", "TU": "tue", "WE": "wed", "TH": "thu", "FR": "fri", "SA": "sat", "SU": "sun"}
                day_parts = []
                for d in byday.split(","):
                    d = d.strip()
                    day_parts.append(dow_map.get(d, d.lower()))
                cron_kwargs["day_of_week"] = ",".join(day_parts)
            # If cron_kwargs is empty (no BYHOUR/BYMINUTE), fall back to interval
            if cron_kwargs:
                return "cron", cron_kwargs

        # Otherwise convert to interval-based scheduling
        interval = _extract_interval(parts, default=1)
        if freq == "SECONDLY":
            return "interval", {"seconds": interval}
        if freq == "MINUTELY":
            return "interval", {"minutes": interval}
        if freq == "HOURLY":
            return "interval", {"hours": interval}
        if freq == "DAILY":
            return "interval", {"days": interval}
        if freq == "WEEKLY":
            return "interval", {"weeks": interval}

    except Exception as e:
        logger.error(f"⚠️ Failed to parse RRULE '{rrule_str}': {e}")

    # fallback
    return "interval", {"minutes": 1}


def register_all_tasks(sched):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, schedule_rule FROM task WHERE enabled=1")
    rows = cur.fetchall()
    for tid, rule in rows:
        try:
            trigger_type, kwargs = parse_rrule_to_kwargs(rule)
            if trigger_type == "interval":
                sched.add_job(run_task, "interval", args=[tid], **kwargs)
            else:  # cron
                # Use CronTrigger to schedule at wall-clock times (respects timezone set on scheduler)
                trigger = CronTrigger(**kwargs)
                sched.add_job(run_task, trigger=trigger, args=[tid])
            print(f"🕒 Registered task {tid} ({trigger_type}: {kwargs})")
        except Exception as e:
            logger.error(f"⚠️ Could not register task {tid}: {e}")
    conn.close()


def start():
    sched = BackgroundScheduler(timezone=IST)
    register_all_tasks(sched)
    sched.start()

    # print detailed job list for quick verification
    jobs = sched.get_jobs()
    if jobs:
        print("🕒 Jobs registered:")
        for j in jobs:
            try:
                print("  - id:", j.id, "next_run:", j.next_run_time, "trigger:", str(j.trigger))
            except Exception:
                print("  - id:", j.id, "trigger:", str(j.trigger))
    else:
        print("🕒 No jobs registered.")

    print("✅ Scheduler started. Press Ctrl+C to exit.")

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sched.shutdown()
        print("🛑 Scheduler stopped.")
