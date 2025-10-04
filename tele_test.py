import asyncio, aiohttp, os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8032892212:AAGyrhpqjUEhzqzWP7mg6Ut-caXAmxcuWx0")
CHAT_ID = os.getenv("CHAT_ID", "5292005628")

async def main():
    async with aiohttp.ClientSession() as s:
        # ✅ Note the "/bot" prefix before the token
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": "✅ Async test via aiohttp"}
        async with s.post(url, json=payload) as r:
            print("HTTP", r.status)
            print(await r.text())

asyncio.run(main())
