# src/tools/messaging.py
import os
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv

# Force-load environment variables from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger("ai_agent")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def _send_async(chat_id: str, text: str, parse_mode: str | None = None):
    """Send a Telegram message asynchronously with optional parse mode."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            body = await resp.text()
            if resp.status != 200:
                logger.error(f"Telegram error {resp.status}: {body}")
                print(f"❌ Telegram error {resp.status}: {body}")
            else:
                logger.info(f"✅ Sent Telegram message to {chat_id}: {text}")
                print(f"✅ Telegram message sent to {chat_id}: {text}")


def send_message(chat_id: str, text: str, parse_mode: str | None = None):
    """Wrapper for _send_async so you can call send_message(chat_id, text, parse_mode='Markdown')."""
    try:
        asyncio.run(_send_async(chat_id, text, parse_mode))
    except Exception as e:
        logger.error(f"❌ Failed to send message: {e}")
        print("❌ Telegram send error:", e)



if __name__ == "__main__":
    send_message(CHAT_ID, "✅ Hello Nishtha! Test message from AI Micro Agent.", parse_mode="Markdown")
