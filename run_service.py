# -*- coding: utf-8 -*-
from src.db import init_db
from src.scheduler import start, register_all_tasks
from src.config import TELEGRAM_CHAT_ID
from src.utils import setup_logger
logger = setup_logger()
logger.info("Service started successfully")


if __name__ == '__main__':
    init_db()
    register_all_tasks(TELEGRAM_CHAT_ID)
    start()
    print('Scheduler started. Press Ctrl+C to exit.')
    import time
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print('Shutting down')