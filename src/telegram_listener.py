# src/telegram_listener.py
import os
import time
import json
import re
import threading
import datetime
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# --- Load environment ---
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# --- local imports (keep ordering/chat/registration logic intact) ---
from src.db import get_conn, create_task
from src.tools.messaging import send_message
from src.tools import orders

# planner helpers from your planner module (uses Ollama)
from src.planner import call_ollama, extract_json_from_text

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("❌ TELEGRAM_BOT_TOKEN missing in .env")
TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = os.path.join(os.path.dirname(__file__), ".tg_offset")

# --- Scheduler (use pytz for APScheduler compatibility) ---
TZ = pytz.timezone("Asia/Kolkata")
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.start()


# -------------------- small helpers --------------------
def load_offset():
    try:
        with open(OFFSET_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_offset(offset):
    try:
        with open(OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception:
        pass


def register_user(chat_id, name, username):
    """Auto-register/update a user in user_registry (keeps existing logic)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            name TEXT,
            username TEXT,
            last_seen TEXT
        )
    """)
    conn.commit()
    now = datetime.datetime.now(TZ).isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO user_registry (chat_id, name, username, last_seen)
        VALUES (?, ?, ?, ?)
    """, (str(chat_id), name, username, now))
    conn.commit()
    conn.close()


def parse_rrule_to_interval_kwargs(rrule_str: str):
    """
    Very small parser for the RRULE forms we use:
    - RRULE:FREQ=SECONDLY;INTERVAL=5  -> {"seconds": 5}
    - RRULE:FREQ=MINUTELY;INTERVAL=2  -> {"minutes": 2}
    - RRULE:FREQ=HOURLY;INTERVAL=1    -> {"hours": 1}
    - RRULE:FREQ=DAILY;INTERVAL=1     -> {"days": 1}
    - RRULE:FREQ=WEEKLY;INTERVAL=1    -> {"weeks": 1}
    For ONCE: we expect RUN_AT=ISO timestamp (handled separately).
    """
    if not rrule_str or not rrule_str.startswith("RRULE:"):
        return None
    parts = {}
    try:
        rule = rrule_str.replace("RRULE:", "")
        for kv in rule.split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                parts[k.strip()] = v.strip()
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
    except Exception:
        return None
    return None


def schedule_job_for_task(task_id: int, params: dict, schedule_rule: str):
    """
    Given DB task id + params (internal plan) and schedule_rule, schedule an APScheduler job.
    params must contain: params["calls"][0]["args"]["chat_id"] and ["text"]
    """
    try:
        chat_id = str(params["calls"][0]["args"]["chat_id"])
        text = params["calls"][0]["args"]["text"]
    except Exception:
        return False

    job_id = f"reminder-{task_id}"

    # remove previously scheduled job with same id
    existing = scheduler.get_job(job_id)
    if existing:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

    # ONCE with RUN_AT
    if schedule_rule and "FREQ=ONCE" in schedule_rule:
        m = re.search(r"RUN_AT=([^;]+)", schedule_rule)
        if m:
            try:
                run_dt = datetime.datetime.fromisoformat(m.group(1))
                if run_dt.tzinfo is None:
                    run_dt = TZ.localize(run_dt)
                scheduler.add_job(lambda c=chat_id, t=text: send_message(c, t),
                                  trigger=DateTrigger(run_date=run_dt),
                                  id=job_id, replace_existing=True)
                return True
            except Exception as e:
                print("⚠️ schedule_job_for_task (ONCE) error:", e)
                return False

    # recurring intervals
    kw = parse_rrule_to_interval_kwargs(schedule_rule)
    if kw:
        try:
            # create IntervalTrigger with TZ and schedule
            trig = IntervalTrigger(timezone=TZ, **kw)
            scheduler.add_job(lambda c=chat_id, t=text: send_message(c, t),
                              trigger=trig, id=job_id, replace_existing=True)
            return True
        except Exception as e:
            print("⚠️ schedule_job_for_task (interval) error:", e)
            return False

    # fallback: schedule once in 60 seconds
    try:
        run_dt = datetime.datetime.now(TZ) + datetime.timedelta(seconds=60)
        scheduler.add_job(lambda c=chat_id, t=text: send_message(c, t),
                          trigger=DateTrigger(run_date=run_dt),
                          id=job_id, replace_existing=True)
        return True
    except Exception as e:
        print("⚠️ schedule_job_for_task fallback error:", e)
        return False


def persist_task_and_schedule(user_chat_id: str, plan_obj: dict):
    """
    Save task in DB (try create_task; fallback to direct insert),
    then schedule it with APScheduler.
    Returns task_id or None.
    """
    # build internal plan for this user's chat
    internal = {
        "plan": plan_obj.get("task_type", "reminder"),
        "calls": [
            {
                "tool": "messaging.send_message",
                "args": {"chat_id": str(user_chat_id), "text": plan_obj.get("text", "Reminder")}
            }
        ]
    }

    # find user_id from user_registry if possible
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user_registry WHERE chat_id=?", (str(user_chat_id),))
    r = cur.fetchone()
    if r:
        user_id = r[0]
    else:
        user_id = 1

    conn.close()

    # try create_task() first (if available/signature matches)
    try:
        tid = create_task(user_id, plan_obj.get("task_type", "reminder"), internal, plan_obj.get("schedule_rule", "RRULE:FREQ=MINUTELY;INTERVAL=1"), 1)
    except Exception:
        # fallback direct SQL (supports common schema)
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO task (user_id, task_type, params_json, schedule_rule, enabled) VALUES (?, ?, ?, ?, ?)",
                        (user_id, plan_obj.get("task_type", "reminder"), json.dumps(internal), plan_obj.get("schedule_rule", "RRULE:FREQ=MINUTELY;INTERVAL=1"), 1))
            conn.commit()
            tid = cur.lastrowid
            conn.close()
        except Exception as e:
            print("❌ persist_task_and_schedule DB insert failed:", e)
            return None

    # schedule in APScheduler
    scheduled = schedule_job_for_task(tid, internal, plan_obj.get("schedule_rule", ""))
    return tid if scheduled else None


def restore_saved_reminders_from_db():
    """On startup, schedule all enabled reminders from DB."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, params_json, schedule_rule FROM task WHERE enabled=1")
        rows = cur.fetchall()
        conn.close()
        for tid, params_json, rule in rows:
            try:
                params = json.loads(params_json) if isinstance(params_json, str) else params_json
            except Exception:
                continue
            # schedule each task (idempotent because scheduler will replace jobs with same id)
            schedule_job_for_task(tid, params, rule or "")
    except Exception as e:
        print("⚠️ Failed to restore reminders from DB:", e)


# restore tasks at start
restore_saved_reminders_from_db()


# -------------------- main message processing (ORDER + CHAT logic kept intact) --------------------
def schedule_place_order(delay_seconds, buyer_chat_id, store_identifier, item):
    def job():
        try:
            orders.place_order(str(buyer_chat_id), store_identifier, item)
        except Exception as e:
            print("⚠️ scheduled order failed:", e)
    t = threading.Timer(delay_seconds, job)
    t.daemon = True
    t.start()
    return t


def process_message(msg):
    try:
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id"))
        username = chat.get("username")
        display_name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or username or ""
        text = msg.get("text") or msg.get("caption") or ""
        if not text:
            return


        # keep user registry logic unchanged
        register_user(chat_id, display_name, username)
        text_lower = text.strip().lower()

        # keep buyer <-> store chat forwarding logic unchanged
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS order_chat_session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    buyer_chat_id TEXT,
                    store_chat_id TEXT,
                    active INTEGER DEFAULT 1
                )
            """)
            conn.commit()
            cur.execute("""
                SELECT id, order_id, buyer_chat_id, store_chat_id
                FROM order_chat_session
                WHERE active=1 AND (buyer_chat_id=? OR store_chat_id=?)
            """, (chat_id, chat_id))
            sess = cur.fetchone()
            conn.close()
            if sess:
                sess_id, order_id, buyer_cid, store_cid = sess
                # endchat preserved
                if text.strip().lower() == "/endchat":
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE order_chat_session SET active=0 WHERE id=?", (sess_id,))
                    conn.commit()
                    conn.close()
                    send_message(buyer_cid, "💬 Chat closed.")
                    send_message(store_cid, "💬 Chat closed.")
                    return
                target = store_cid if chat_id == buyer_cid else buyer_cid
                prefix = "👤 Customer" if chat_id == buyer_cid else "🏪 Store"
                send_message(target, f"{prefix}:\n{text}")
                return
        except Exception:
            pass

        text_lower = text.strip().lower()

        # --- /start (keep exactly) ---
        if text_lower.startswith("/start"):
            send_message(chat_id,
                "👋 Hello! I'm your AI ordering + reminder assistant.\n\n"
                "🛒 Use `/remind order <item> from <store>` to place an order.\n"
                "⏰ Use `/remind <task> in 5 minutes` or `/remind <task> every 2 hours` for reminders.\n\n"
                "Example:\n"
                "`/remind remind me to blink every 5 seconds`\n"
                "`/remind order milk from Capital Store`"
            )
            return

        # --- /whoami (kept) ---
        if text_lower.startswith("/whoami"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT name, username, last_seen FROM user_registry WHERE chat_id=?", (chat_id,))
            user_info = cur.fetchone()
            conn.close()
            if user_info:
                name, uname, last_seen = user_info
                send_message(chat_id, f"🆔 *Chat ID:* `{chat_id}`\n👤 *Name:* {name}\n📛 *Username:* @{uname or '—'}\n⏱ *Last Seen:* {last_seen}")
            else:
                send_message(chat_id, f"⚠️ You’re not registered yet. Try sending /start.")
            return
        # 🧾 --- list reminders ---
        if text_lower.startswith("/list_reminders"):
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT id, params_json, schedule_rule, enabled FROM task WHERE enabled=1")
                rows = cur.fetchall()
                conn.close()

                if not rows:
                    send_message(chat_id, "ℹ️ You have no active reminders.")
                    return

                lines = []
                for tid, params_json, rule, enabled in rows:
                    try:
                        params = json.loads(params_json)
                        msg_text = params["calls"][0]["args"].get("text", "")
                    except Exception:
                        msg_text = "(unreadable)"
                    lines.append(f"🆔 *{tid}* → {msg_text}\n   ⏱ {rule}")

                msg_body = "📋 *Active Reminders:*\n\n" + "\n\n".join(lines)
                msg_body += "\n\nUse `/delete_reminder <id>` to delete a reminder."
                send_message(chat_id, msg_body)
            except Exception as e:
                send_message(chat_id, f"⚠️ Failed to list reminders: {e}")
            return

        # ❌ --- delete reminder ---
        if text_lower.startswith("/delete_reminder"):
            parts = text.split()
            if len(parts) < 2:
                send_message(chat_id, "Usage: /delete_reminder <reminder_id>")
                return

            try:
                rid = int(parts[1])
            except ValueError:
                send_message(chat_id, "Please provide a valid numeric reminder ID.")
                return

            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("UPDATE task SET enabled=0 WHERE id=?", (rid,))
                conn.commit()
                conn.close()

                job_id = f"reminder-{rid}"
                job = scheduler.get_job(job_id)
                if job:
                    job.remove()

                send_message(chat_id, f"✅ Reminder *{rid}* deleted successfully.")
            except Exception as e:
                send_message(chat_id, f"⚠️ Could not delete reminder {rid}: {e}")
            return

        # --- /remind command (first check order syntax) ---
        if text_lower.startswith("/remind"):
            parts = text.split(" ", 1)
            if len(parts) < 2:
                send_message(chat_id, "Usage: /remind <your instruction>")
                return

            nl_original = parts[1].strip()
            nl = nl_original.lower()

            # ordering branch (unchanged)
            if "order" in nl and "from" in nl:
                idx = nl.rfind(" from ")
                if idx == -1:
                    send_message(chat_id, "❌ Couldn't parse store name.")
                    return
                item_part = nl_original[:idx].replace("order", "", 1).strip()
                store_part = nl_original[idx + len(" from "):].strip()
                m = re.search(r"in (\d+)\s*(second|seconds|minute|minutes|hour|hours)\b", nl)
                if m:
                    num = int(m.group(1))
                    unit = m.group(2)
                    delay = num if "second" in unit else num * 60 if "minute" in unit else num * 3600
                    schedule_place_order(delay, chat_id, store_part, item_part)
                    send_message(chat_id, f"✅ Scheduled order for *{item_part}* from *{store_part}* in {num} {unit}.")
                else:
                    orders.place_order(chat_id, store_part, item_part)
                return

            # ----- Reminder branch (LLM + DB + schedule) -----
            # acknowledge and call Ollama like before
            send_message(chat_id, f"Got it — I'll create a reminder for: \"{nl_original}\". Processing with Ollama...")
            # build system prompt (same style as planner.parse_command)
            system_prompt = (
                "You are a JSON-only generator. Convert the user's instruction into a single JSON object "
                "and output only that JSON object and nothing else. The JSON must have exactly these keys: "
                "\"task_type\" (one of 'reminder'|'bill_link'|'email_summary'), "
                "\"schedule_rule\" (an iCalendar RRULE string like 'RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0'), "
                "\"text\" (the message to send).\n\n"
                "Examples:\n"
                "Input: \"Remind me to drink water every 2 hours\"\n"
                "Output:\n"
                '{\"task_type\":\"reminder\",\"schedule_rule\":\"RRULE:FREQ=HOURLY;INTERVAL=2\",\"text\":\"Drink water\"}\n\n'
                "Input: \"Send me a message every Monday at 6pm saying buy groceries\"\n"
                "Output:\n"
                '{\"task_type\":\"reminder\",\"schedule_rule\":\"RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=18;BYMINUTE=0\",\"text\":\"Buy groceries\"}\n\n'
                "Now convert this input to JSON:\n"
                f"Input: {nl_original}\n"
                "Output:"
            )

            raw = None
            try:
                raw = call_ollama(system_prompt)
            except Exception as e:
                print("⚠️ Ollama call failed:", e)

            plan = None
            if raw:
                # debug preview trimmed
                preview = raw.strip()
                if len(preview) > 800:
                    preview = preview[:800] + " ... (truncated)"
                print("🔎 Model raw response preview:")
                print(preview)
                try:
                    plan = extract_json_from_text(raw)
                except Exception as e:
                    print("⚠️ Failed to parse LLM response:", e)

            # fallback if LLM fails
            if not plan or not isinstance(plan, dict):
                # try to normalize text into reminder text
                fallback_text = nl_original.replace("remind me to", "").strip().capitalize()
                plan = {
                    "task_type": "reminder",
                    "schedule_rule": "RRULE:FREQ=HOURLY;INTERVAL=2",
                    "text": fallback_text or "Reminder"
                }
                print("⚠️ Using fallback plan:", plan)

            # small heuristic override: if user explicitly used 'second/minute/hour/day' in input, prefer that
            txt_lower = nl_original.lower()
            if "second" in txt_lower:
                rrule = "RRULE:FREQ=SECONDLY;INTERVAL=1"
            elif "minute" in txt_lower:
                rrule = "RRULE:FREQ=MINUTELY;INTERVAL=1"
            elif "hour" in txt_lower:
                rrule = "RRULE:FREQ=HOURLY;INTERVAL=1"
            elif "day" in txt_lower:
                rrule = "RRULE:FREQ=DAILY;INTERVAL=1"
            else:
                # keep LLM provided schedule_rule if present
                rrule = plan.get("schedule_rule", "RRULE:FREQ=HOURLY;INTERVAL=2")
            plan["schedule_rule"] = rrule

            # store in DB + schedule job
            tid = persist_task_and_schedule(chat_id, plan)
            if tid:
                send_message(chat_id, f"✅ Created reminder (task id={tid}). I will remind you per the schedule.")
            else:
                send_message(chat_id, "⚠️ Failed to create reminder. Please try again.")
            return

        # unknown - ignore or simple help (kept simple)
        # send_message(chat_id, "Unknown command. Use /remind or /endchat.")
    except Exception as e:
        print("⚠️ process_message errror:", e)


def handle_callback_query(callback_query):
    try:
        data = callback_query.get("data", "")
        from_user = callback_query.get("from", {})
        user_id = str(from_user.get("id"))
        # route callback to orders module (keeps existing behavior)
        if data.startswith(("accept_", "out_")):
            orders.handle_store_callback(data, user_id)
        else:
            orders.handle_buyer_callback(data, user_id)
    except Exception as e:
        print("⚠️ handle_callback_query error:", e)


def main_loop():
    offset = load_offset()
    print("✅ Telegram listener started (polling getUpdates).")
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{TG_BASE}/getUpdates", params=params, timeout=40)
            data = r.json()
            if not data.get("ok"):
                time.sleep(2)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                save_offset(offset)
                if "message" in upd:
                    process_message(upd["message"])
                elif "callback_query" in upd:
                    handle_callback_query(upd["callback_query"])
            time.sleep(0.5)
        except Exception as e:
            print("⚠️ Telegram listener error:", e)
            time.sleep(2)


if __name__ == "__main__":
    main_loop()
