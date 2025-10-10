import requests
import json
import re
from .db import create_task
from .config import OLLAMA_URL, OLLAMA_MODEL, TELEGRAM_CHAT_ID

def call_ollama(prompt: str):
    """Call local Ollama and reconstruct streamed responses into one string."""
    try:
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": True}
        with requests.post(f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=60) as res:
            output = ""
            for line in res.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "response" in data:
                        output += data["response"]
                except json.JSONDecodeError:
                    continue
            return output.strip()
    except Exception as e:
        print("⚠️ Ollama call failed:", e)
        return None


def extract_json_from_text(text: str):
    """Try to extract a JSON object from Ollama output."""
    if not text:
        raise ValueError("No text to parse")
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"(\{(?:.|\s)*\})", text)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Could not extract valid JSON from model output")


def detect_store_and_item(text: str):
    """
    Naive rule-based extraction for store names and items.
    e.g. 'Order milk every 2 days from Capital Store' →
         {'item': 'milk', 'store': 'Capital Store'}
    """
    store_match = re.search(r"from\s+([A-Z][a-zA-Z0-9\s]+(?:Store|Mart|Shop|Market))", text, re.IGNORECASE)
    item_match = re.search(r"order\s+(\w+)", text, re.IGNORECASE)

    store = store_match.group(1).strip() if store_match else None
    item = item_match.group(1).strip() if item_match else None
    return {"item": item, "store": store}


def build_internal_plan(plan_obj):
    """Return an internal MCP plan for DB storage."""
    text = plan_obj.get("text", "Reminder")
    task_type = plan_obj.get("task_type", "reminder")
    extra = plan_obj.get("extra", {})

    if task_type == "order":
        # message the store instead of user
        store_chat_id = extra.get("store_chat_id", "STORE_CHAT_PLACEHOLDER")
        return {
            "plan": task_type,
            "calls": [
                {
                    "tool": "orders.place_order",
                    "args": {
                        "user_chat_id": TELEGRAM_CHAT_ID,
                        "store_chat_id": store_chat_id,
                        "item": extra.get("item", text),
                        "store": extra.get("store", "Unknown Store"),
                    },
                }
            ],
        }
    elif task_type == "email_summary":
        return {
            "plan": task_type,
            "calls": [
                {
                    "tool": "email.summary",
                    "args": {"chat_id": TELEGRAM_CHAT_ID}
                }
            ],
        }

    # default reminder
    return {
        "plan": task_type,
        "calls": [
            {
                "tool": "messaging.send_message",
                "args": {"chat_id": TELEGRAM_CHAT_ID, "text": text},
            }
        ],
    }


def parse_command(command_text: str, user_id: int = 1):
    """Interpret a natural-language command and save as a structured task."""
    system_prompt = (
        "You are a JSON-only generator. Convert the user's instruction into a single JSON object "
        "and output only that JSON object and nothing else. The JSON must have exactly these keys: "
        "\"task_type\" (one of 'reminder'|'bill_link'|'email_summary'|'order'), "
        "\"schedule_rule\" (an iCalendar RRULE string like 'RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0'), "
        "\"text\" (the message to send).\n\n"
        "Examples:\n"
        "Input: \"Remind me to drink water every 2 hours\"\n"
        "Output:\n"
        '{\"task_type\":\"reminder\",\"schedule_rule\":\"RRULE:FREQ=HOURLY;INTERVAL=2\",\"text\":\"Drink water\"}\n\n'
        "Input: \"Order milk every 2 days from Capital Store\"\n"
        "Output:\n"
        '{\"task_type\":\"order\",\"schedule_rule\":\"RRULE:FREQ=DAILY;INTERVAL=2\",\"text\":\"Order milk from Capital Store\"}\n\n'
        "Input: \"Give me an email summary every day at 10 am\"\n"
        "Output:\n"
        "{\"task_type\":\"email_summary\",\"schedule_rule\":\"RRULE:FREQ=DAILY;BYHOUR=10;BYMINUTE=0\",\"text\":\"Email Summary\"}\n\n"
        "Now convert this input to JSON:\n"
        f"Input: {command_text}\nOutput:"
    )

    raw = call_ollama(system_prompt)
    plan = None
    if raw:
        try:
            plan = extract_json_from_text(raw)
        except Exception as e:
            print("⚠️ Failed to parse LLM response:", e)

    if not plan or not isinstance(plan, dict):
        # fallback
        plan = {
            "task_type": "reminder",
            "schedule_rule": "RRULE:FREQ=DAILY;INTERVAL=1",
            "text": command_text,
        }

    # detect store & item
    store_info = detect_store_and_item(command_text)
    if store_info["store"]:
        plan["task_type"] = "order"
        plan["extra"] = store_info
        print(f"🛒 Detected order task → Item: {store_info['item']} from {store_info['store']}")

    internal = build_internal_plan(plan)
    # 🛒 Detect if it's an order
    if "order" in command_text.lower() and "from" in command_text.lower():
        try:
            parts = command_text.lower().split("from")
            item = parts[0].replace("order", "").strip()
            store_name = parts[1].strip()
            print(f"🛒 Detected order task → Item: {item} from {store_name}")

            from src.tools import orders
            store = orders.find_store_by_name(store_name)

            if store:
                orders.send_order_to_store(store, item, TELEGRAM_CHAT_ID)
                print(f"✅ Order sent to {store_name}")
            else:
                from src.tools.messaging import send_message
                send_message(TELEGRAM_CHAT_ID, f"⚠️ I can’t find *{store_name}* in the store list.\nAsk them to register using /register_store {store_name}.")
        except Exception as e:
            print(f"⚠️ Order parsing failed: {e}")

    task_id = create_task(user_id, plan["task_type"], internal, plan["schedule_rule"], 1)
    print(f"✅ Task created from natural language (id={task_id})")
    print(json.dumps(plan, indent=2))
    return plan
