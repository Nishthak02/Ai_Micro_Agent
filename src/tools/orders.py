import os
import json
import requests
import datetime
from dotenv import load_dotenv
from src.db import get_conn
from src.tools.messaging import send_message

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ────────────────────────────────────────────────
# 🧩 Helper: Resolve store from registry
# ────────────────────────────────────────────────
def get_chat_id_by_name(name: str):
    """Fetch chat_id by name from user_registry."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM user_registry WHERE LOWER(name)=?", (name.lower(),))
    row = cur.fetchone()
    conn.close()
    return str(row[0]) if row else None


# ────────────────────────────────────────────────
# 🛒 Place an order (Buyer → Store)
# ────────────────────────────────────────────────
def place_order(buyer_chat_id: str, store_identifier: str, item: str):
    """Sends an order message to the store with inline buttons."""
    store_chat_id = get_chat_id_by_name(store_identifier)
    if not store_chat_id:
        send_message(
            buyer_chat_id,
            f"⚠️ I couldn't find *{store_identifier}* in the user registry.\n"
            f"Ask them to start this bot first using /start."
        )
        return

    # Create order_status table if not exists
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_chat_id TEXT,
            store_chat_id TEXT,
            store_name TEXT,
            item TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()

    # Insert order record
    cur.execute(
        """
        INSERT INTO order_status (
            buyer_chat_id, store_chat_id, store_name, item, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(buyer_chat_id),
            str(store_chat_id),
            store_identifier,
            item,
            "pending",
            datetime.datetime.now().isoformat(),
            datetime.datetime.now().isoformat(),
        ),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()

    # Send order message to store
    payload = {
        "chat_id": store_chat_id,
        "text": f"🛒 *New Order from Customer*\n\n📦 Item: *{item}*\nWould you like to accept it?",
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [
                    {"text": "✅ Accept Order", "callback_data": f"accept_{order_id}"},
                    {"text": "❌ Out of Stock", "callback_data": f"out_{order_id}"}
                ]
            ]
        })
    }

    res = requests.post(f"{TG_BASE}/sendMessage", data=payload)
    if res.status_code == 200:
        send_message(buyer_chat_id, f"✅ Order sent to *{store_identifier}* for *{item}*.")
    else:
        send_message(buyer_chat_id, f"⚠️ Failed to deliver order to *{store_identifier}*.")
        print("❌ Telegram API error:", res.text)


# ────────────────────────────────────────────────
# 🏪 Store-side button handling
# ────────────────────────────────────────────────
def handle_store_callback(callback_data: str, store_chat_id: str):
    """Handles store's button responses."""
    try:
        action, order_id_str = callback_data.split("_", 1)
        order_id = int(order_id_str)
    except Exception:
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT buyer_chat_id, item, store_name FROM order_status WHERE id=?", (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return

    buyer_chat_id, item, store_name = row

    # Store accepts the order
    if action == "accept":
        cur.execute(
            "UPDATE order_status SET status=?, updated_at=? WHERE id=?",
            ("accepted", datetime.datetime.now().isoformat(), order_id)
        )
        conn.commit()
        send_message(buyer_chat_id, f"✅ *{store_name}* accepted your order for *{item}*! Proceed with payment 💸.")
        send_message(store_chat_id, f"👍 You accepted the order for *{item}*.")

    # Store marks item as out of stock
    elif action == "out":
        cur.execute(
            "UPDATE order_status SET status=?, updated_at=? WHERE id=?",
            ("out_of_stock", datetime.datetime.now().isoformat(), order_id)
        )
        conn.commit()

        payload = {
            "chat_id": buyer_chat_id,
            "text": (
                f"⚠️ *{store_name}* reports *{item}* is out of stock.\n"
                f"Would you like to skip or chat with the store?"
            ),
            "parse_mode": "Markdown",
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [
                        {"text": "⏭ Skip This Time", "callback_data": f"skip_{order_id}"},
                        {"text": "💬 Chat with Store", "callback_data": f"chat_{order_id}"}
                    ]
                ]
            })
        }

        requests.post(f"{TG_BASE}/sendMessage", data=payload)
        send_message(store_chat_id, f"📦 You marked *{item}* as out of stock.")

    conn.close()


# ────────────────────────────────────────────────
# 👩‍💼 Buyer-side button handling (Skip / Chat)
# ────────────────────────────────────────────────
def handle_buyer_callback(callback_data: str, buyer_chat_id: str):
    """Handles buyer's Skip / Chat actions."""
    try:
        action, order_id_str = callback_data.split("_", 1)
        order_id = int(order_id_str)
    except Exception:
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT store_chat_id, item, store_name FROM order_status WHERE id=?", (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return

    store_chat_id, item, store_name = row

    # Buyer skips the order
    if action == "skip":
        cur.execute(
            "UPDATE order_status SET status=?, updated_at=? WHERE id=?",
            ("skipped", datetime.datetime.now().isoformat(), order_id)
        )
        conn.commit()
        send_message(store_chat_id, f"ℹ️ Customer skipped the order for *{item}* this time.")
        send_message(buyer_chat_id, f"✅ You skipped the order from *{store_name}* this time.")

    # Buyer wants to chat with store
    elif action == "chat":
        send_message(buyer_chat_id, f"💬 Starting a chat with *{store_name}*.")
        send_message(store_chat_id, f"💬 Customer wants to chat regarding *{item}*.")

        # Create or update active chat session
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

        cur.execute(
            "INSERT INTO order_chat_session (order_id, buyer_chat_id, store_chat_id, active) VALUES (?, ?, ?, 1)",
            (order_id, str(buyer_chat_id), str(store_chat_id))
        )
        conn.commit()

        send_message(buyer_chat_id, "💬 You can now chat directly. Type /endchat to finish.")
        send_message(store_chat_id, "💬 You are now in a chat with the customer. Type /endchat to end the session.")

    conn.close()
