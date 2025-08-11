# utils/monitoring.py
#♦️loggin+alerthelper+ratatongs log

import logging
from logging.handlers import RotatingFileHandler
import os
import traceback
import httpx

from utils.config import DB_PATH, TELEGRAM_BOT_TOKEN

LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

def configure_logging(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)
    # Console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # Rotating file
    fh = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

# Async destekli Telegram alert
def telegram_alert(message: str):
    token = TELEGRAM_BOT_TOKEN
    chat_id = os.getenv("ALERT_CHAT_ID")
    if not token or not chat_id:
        return

    try:
        # Async çalıştır ama bekleme (fire and forget)
        async def send():
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": chat_id, "text": f"[ALERT] {message}"}
                )

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(send())  # mevcut loop'a ekle
        except RuntimeError:
            # loop yoksa blocking çalıştır
            asyncio.run(send())

    except Exception:
        traceback.print_exc()
        
