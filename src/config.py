import os
from dotenv import load_dotenv
from datetime import time


load_dotenv()


TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
IMAP_USER = os.getenv('IMAP_USER')
IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'ollama-model')
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
QUIET_HOURS_START = os.getenv('QUIET_HOURS_START', '22:00')
QUIET_HOURS_END = os.getenv('QUIET_HOURS_END', '07:00')
AMOUNT_CAP = float(os.getenv('AMOUNT_CAP', '20000'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///ai_agent.db')