# src/tools/orchestrator.py
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from src.db import get_conn

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

if not BOT_TOKEN:
    raise SystemExit("❌ TELEGRAM_BOT_TOKEN missing in .env")

# --- Telegram Helpers ---

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send a message to Telegram (with optional inline buttons)."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    res = requests.post(f"{TG_BASE}/sendMessage", data=payload)
    if not res.ok:
        print(f"❌ Telegram send error {res.status_code}: {res.text}")
    else:
        print(f"✅ Message sent to {chat_id}: {text[:60]}")
    return res


def answer_callback_query(callback_query_id, text=None):
    """Respond to Telegram callback query."""
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(f"{TG_BASE}/answerCallbackQuery", data=payload)


# --- Order Table Helpers ---

def create_order(task_id, buyer_chat_id, store_name, store_chat_id, item):
    """Insert a new order entry in DB."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO order_status (task_id, buyer_chat_id, store_name, store_chat_id, item, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            str(buyer_chat_id),
            store_name,
            str(store_chat_id),
            item,
            "pending",
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    print(f"🛒 Created new order: {item} from {store_name}")
    return True


def update_order_status(order_id, status):
    """Update an order’s status."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE order_status SET status=?, updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), order_id),
    )
    conn.commit()
    conn.close()
    print(f"🔄 Updated order {order_id} → {status}")


# --- Core Logic ---

def send_order_to_store(order_id, store_chat_id, item, buyer_chat_id, store_name):
    """
    Sends an order message to the store with inline buttons.
    The store can either 'Accept Order' or mark 'Out of Stock'.
    """
    text = f"📦 *New Order Received!*\n\n🛍️ Item: *{item}*\n👤 Buyer: `{buyer_chat_id}`"
    buttons = {
        "inline_keyboard": [
            [
                {"text": "✅ Accept Order", "callback_data": f"accept:{order_id}:{buyer_chat_id}"},
                {"text": "❌ Out of Stock", "callback_data": f"out:{order_id}:{buyer_chat_id}"},
            ]
        ]
    }
    send_message(store_chat_id, text, reply_markup=buttons)
    update_order_status(order_id, "pending")
    print(f"📩 Order sent to store: {store_name}")


def handle_store_response(callback_query):
    """
    Handles when the store clicks Accept / Out of Stock.
    """
    data = callback_query.get("data", "")
    from_user = callback_query.get("from", {})
    callback_id = callback_query["id"]

    if not data or ":" not in data:
        answer_callback_query(callback_id, "Invalid response.")
        return

    action, order_id, buyer_chat_id = data.split(":")
    buyer_chat_id = str(buyer_chat_id)

    if action == "accept":
        answer_callback_query(callback_id, "✅ Order accepted!")
        update_order_status(order_id, "accepted")
        send_message(buyer_chat_id, "✅ Your order has been *accepted* by the store!")
    elif action == "out":
        answer_callback_query(callback_id, "❌ Marked as out of stock.")
        update_order_status(order_id, "out_of_stock")

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "⏭ Skip this time", "callback_data": f"skip:{order_id}"},
                    {"text": "💬 Chat with Store", "callback_data": f"chat:{order_id}:{from_user.get('id')}"}
                ]
            ]
        }
        send_message(
            buyer_chat_id,
            "❌ The product is *out of stock*.\nWould you like to skip this order or chat with the store?",
            reply_markup=buttons,
        )


def handle_buyer_response(callback_query):
    """Handles when the buyer selects Skip or Chat with Store."""
    data = callback_query.get("data", "")
    callback_id = callback_query["id"]

    if not data:
        return

    if data.startswith("skip:"):
        _, order_id = data.split(":")
        update_order_status(order_id, "skipped")
        answer_callback_query(callback_id, "⏭ Skipped this order.")
        print(f"⏭ Buyer skipped order {order_id}")

    elif data.startswith("chat:"):
        _, order_id, store_chat_id = data.split(":")
        answer_callback_query(callback_id, "💬 Starting chat with store...")
        send_message(store_chat_id, "💬 Buyer wants to chat with you regarding the order.")
        print(f"💬 Chat initiated between buyer and store (order {order_id}).")
