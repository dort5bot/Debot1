# utils/config.py
#♦️merkezi config dotenv

import os
from dotenv import load_dotenv

_load_path = os.getenv("ENV_PATH", ".env")
load_dotenv(_load_path)

def get_env(key: str, default=None):
    val = os.getenv(key)
    return val if val is not None else default

# typed helpers
PAPER_MODE = get_env("PAPER_MODE", "true").lower() in ("1","true","yes")
STREAM_SYMBOLS = [s.strip().upper() for s in get_env("STREAM_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")]
STREAM_INTERVAL = get_env("STREAM_INTERVAL", "1m")
DB_PATH = get_env("DB_PATH", "data/paper_trades.db")
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", "")
BINANCE_API_KEY = get_env("BINANCE_API_KEY", "")
BINANCE_API_SECRET = get_env("BINANCE_API_SECRET", "")
BINANCE_FAPI_KEY = get_env("BINANCE_FAPI_KEY", BINANCE_API_KEY)
BINANCE_FAPI_SECRET = get_env("BINANCE_FAPI_SECRET", BINANCE_API_SECRET)

# tuning
STREAM_GROUP_SIZE = int(get_env("STREAM_GROUP_SIZE", "60"))  # how many streams per combined stream
EVALUATOR_WINDOW = int(get_env("EVALUATOR_WINDOW", "12"))   # seconds
EVALUATOR_THRESHOLD = float(get_env("EVALUATOR_THRESHOLD", "0.25"))
RISK_MAX_DAILY_LOSS = float(get_env("RISK_MAX_DAILY_LOSS", "0.05"))  # fraction of equity
