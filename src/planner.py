# src/planner.py
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
                    # Sometimes lines are not JSON, skip
                    continue
            return output.strip()
    except Exception as e:
        print("⚠️ Ollama call failed:", e)
        return None


def extract_json_from_text(text: str):
    """
    Try several strategies to extract a JSON object from the model's text.
    Returns a Python dict or raises ValueError if not found/parsable.
    """
    if not text:
        raise ValueError("No text to parse")

    # 1) If text is exactly JSON, try it
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) Try code fence with ```json ... ```
    m = re.search(r"```json\\s*(\\{.*?\\})\\s*```", text, flags=re.DOTALL)
    if m:
        candidate = m.group(1)
        return json.loads(candidate)

    # 3) Try any { ... } balanced extraction — find the first balanced JSON object
    start = None
    stack = []
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            stack.append("{")
        elif ch == "}":
            if stack:
                stack.pop()
                if not stack and start is not None:
                    candidate = text[start:i+1]
                    # try parsing candidate
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # continue searching for another balanced range
                        start = None
                        stack = []
                        continue

    # 4) Try to find first line that looks like JSON after a colon
    m2 = re.search(r"(\{(?:.|\s)*\})", text)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass

    # nothing worked
    raise ValueError("Could not extract valid JSON from model output")

def build_internal_plan(plan_obj):
    """Given parsed plan_obj with keys, return internal MCP plan for DB storage."""
    text = plan_obj.get("text", "Reminder")
    task_type = plan_obj.get("task_type", "reminder")
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
        f"Input: {command_text}\n"
        "Output:"
    )

    raw = call_ollama(system_prompt)
    plan = None
    if raw:
        # Debug: show the raw response (trimmed)
        preview = raw.strip()
        if len(preview) > 800:
            preview = preview[:800] + " ... (truncated)"
        print("🔎 Model raw response preview:")
        print(preview)
        try:
            plan = extract_json_from_text(raw)
        except Exception as e:
            print("⚠️ Failed to parse LLM response:", e)

    # fallback plan if parsing failed or no model reply
    if not plan or not isinstance(plan, dict):
        fallback_text = command_text
        # Very small heuristic to normalize
        fallback_text = fallback_text.replace("remind me to", "").strip().capitalize()
        plan = {
            "task_type": "reminder",
            "schedule_rule": "RRULE:FREQ=HOURLY;INTERVAL=2",
            "text": fallback_text or "Reminder"
        }
        print("⚠️ Using fallback plan:", plan)

    # Validate keys
    if any(k not in plan for k in ("task_type", "schedule_rule", "text")):
        print("⚠️ Plan missing required keys; using fallback.")
        plan = {
            "task_type": "reminder",
            "schedule_rule": "RRULE:FREQ=HOURLY;INTERVAL=2",
            "text": command_text.replace("remind me to", "").strip().capitalize() or "Reminder"
        }

    internal = build_internal_plan(plan)
    task_id = create_task(user_id, plan["task_type"], internal, plan["schedule_rule"], 1)
    print(f"✅ Task created from natural language (id={task_id})")
    print(json.dumps(plan, indent=2))
    return plan
