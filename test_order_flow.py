"""
test_order_flow.py — simulate a Telegram buyer↔store order flow
Requires: a valid TELEGRAM_BOT_TOKEN in your .env file
"""

import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# -----------------------------------
# CONFIG — replace these with actual chat IDs for testing
# -----------------------------------
BUYER_CHAT_ID = os.getenv("TEST_BUYER_ID", "5292005628")  # your own ID
STORE_CHAT_ID = os.getenv("TEST_STORE_ID", None)           # a friend’s or dummy store account ID

# if you don’t have a store ID yet, we’ll simulate one
SIMULATE_STORE = STORE_CHAT_ID is None

# -----------------------------------
# Helper: Send a message to the bot as a user
# -----------------------------------
def send_user_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    r = requests.post(f"{TG_BASE}/sendMessage", data=payload)
    print(f"➡️ Sent: {text} → chat {chat_id}")
    return r.json()

# -----------------------------------
# Helper: simulate buyer placing an order
# -----------------------------------
def simulate_buyer_order():
    print("\n🧍 Simulating Buyer placing order...")
    send_user_message(BUYER_CHAT_ID, "/remind order milk every 2 days from Capital Store")
    time.sleep(2)
    updates = requests.get(f"{TG_BASE}/getUpdates").json()
    print(json.dumps(updates, indent=2))
    print("✅ Buyer message sent and bot response retrieved.\n")

# -----------------------------------
# Helper: simulate store registering
# -----------------------------------
def simulate_store_register():
    if SIMULATE_STORE:
        print("\n🏪 Creating dummy store registration in DB via /register_store...")
        send_user_message(BUYER_CHAT_ID, "/register_store Capital Store")
        print("✅ Dummy store registered in DB as Capital Store (same chat).")
    else:
        send_user_message(STORE_CHAT_ID, "/register_store Capital Store")
        print("✅ Store registered as Capital Store.\n")

# -----------------------------------
# Helper: simulate store response to order
# -----------------------------------
def simulate_store_response(action="accept"):
    print(f"\n🏪 Simulating store action: {action.upper()}")
    updates = requests.get(f"{TG_BASE}/getUpdates").json()
    result = updates.get("result", [])
    callback_query = None
    for upd in result:
        if "callback_query" in upd:
            cb = upd["callback_query"]
            data = cb.get("data", "")
            if data.startswith("accept") or data.startswith("out_"):
                callback_query = cb
                break
    if not callback_query:
        print("⚠️ No callback_query found in updates.")
        return

    if action == "accept":
        callback_data = callback_query["data"].replace("out_", "accept_")
    else:
        callback_data = callback_query["data"].replace("accept_", "out_")

    print(f"💡 Sending callback: {callback_data}")
    requests.post(
        f"{TG_BASE}/answerCallbackQuery",
        data={"callback_query_id": callback_query["id"], "text": f"Store chose {action}"},
    )

    print("✅ Simulated store callback submitted.\n")

# -----------------------------------
# Run the test sequence
# -----------------------------------
if __name__ == "__main__":
    print("🚀 Starting test order flow...\n")

    if SIMULATE_STORE:
        simulate_store_register()
    simulate_buyer_order()

    print("⏳ Wait 3–5 seconds, then manually check Telegram for messages...")

    # Optionally simulate store action after some delay
    time.sleep(5)
    simulate_store_response("accept")

    print("\n✅ Test run complete. Check buyer & store Telegram chats for results.")
