# utils/monitoring.py
#♦️loggin+alerthelper+ratatongs log

import logging
from logging.handlers import RotatingFileHandler
import os
from utils.config import DB_PATH, TELEGRAM_BOT_TOKEN
import requests
import traceback

LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

def configure_logging(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)
    # console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # rotating file
    fh = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

# simple telegram alert (fire and forget)
def telegram_alert(message: str):
    token = TELEGRAM_BOT_TOKEN
    if not token:
        return
    try:
        chat_id = os.getenv("ALERT_CHAT_ID")
        if not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"[ALERT] {message}"}
        # no blocking; best effort
        requests.post(url, data=payload, timeout=3)
    except Exception:
        traceback.print_exc()
