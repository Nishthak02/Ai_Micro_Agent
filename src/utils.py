import json
from datetime import datetime, timezone
import hashlib
import logging
import sys

sys.stdout.reconfigure(encoding='utf-8')


def now_iso():
    return datetime.now(timezone.utc).isoformat()




def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:10]


def setup_logger():
    logger = logging.getLogger("ai_agent")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler("ai_agent.log", encoding="utf-8")
    fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)

    return logger
