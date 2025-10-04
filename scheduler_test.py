import os
import asyncio
import aiohttp
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv(dotenv_path=".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
IST = pytz.timezone("Asia/Kolkata")  # ✅ Use pytz timezone

async def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            print("HTTP", resp.status, await resp.text())

def job():
    print("🕒 Scheduler fired!")
    asyncio.run(send_message("✅ Reminder from Scheduler Test!"))

if not BOT_TOKEN or not CHAT_ID:
    print("❌ Missing BOT_TOKEN or CHAT_ID in .env")
    exit()

sched = BackgroundScheduler(timezone=IST)  # ✅ timezone fixed
sched.add_job(job, "interval", seconds=5)
sched.start()

print("✅ Scheduler started! Press Ctrl+C to stop.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    sched.shutdown()
    print("🛑 Scheduler stopped.")
