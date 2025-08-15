# utils/config.py
from dataclasses import dataclass, field
from typing import List
import os
from dotenv import load_dotenv

# --- Load dotenv ---
ENV_PATH = os.getenv("ENV_PATH", ".env")
load_dotenv(ENV_PATH)

def get_env(key: str, default=None, cast=None):
    """Env değerini oku ve opsiyonel tip dönüşümü yap."""
    val = os.getenv(key, default)
    if val is not None and cast:
        try:
            if cast == bool:
                val = str(val).lower() in ("1", "true", "yes")
            elif cast == list:
                val = [s.strip().upper() for s in str(val).split(",")]
            else:
                val = cast(val)
        except Exception:
            pass
    return val

# ----------------------------
# Dataclass bazlı config
# ----------------------------

@dataclass
class BinanceConfig:
    """Binance API ve stream parametreleri"""
    API_KEY: str = field(default_factory=lambda: get_env("BINANCE_API_KEY", ""))
    API_SECRET: str = field(default_factory=lambda: get_env("BINANCE_API_SECRET", ""))
    FAPI_KEY: str = field(default_factory=lambda: get_env("BINANCE_FAPI_KEY", get_env("BINANCE_API_KEY", "")))
    FAPI_SECRET: str = field(default_factory=lambda: get_env("BINANCE_FAPI_SECRET", get_env("BINANCE_API_SECRET", "")))
    CONCURRENCY: int = field(default_factory=lambda: get_env("BINANCE_CONCURRENCY", 8, int))
    TICKER_TTL: float = field(default_factory=lambda: get_env("BINANCE_TICKER_TTL", 12.0, float))

@dataclass
class APIOConfig:
    """AP / IO parametreleri"""
    WHALE_USD_THRESHOLD: float = field(default_factory=lambda: get_env("WHALE_USD_THRESHOLD", 50000.0, float))
    TRADES_LIMIT: int = field(default_factory=lambda: get_env("TRADES_LIMIT", 500, int))
    TOP_SYMBOLS_FOR_IO: int = field(default_factory=lambda: get_env("TOP_SYMBOLS_FOR_IO", 30, int))
    IO_CONCURRENCY: int = field(default_factory=lambda: get_env("IO_CONCURRENCY", 8, int))

@dataclass
class BotConfig:
    """Genel bot parametreleri"""
    DEBUG: bool = field(default_factory=lambda: get_env("DEBUG", False, bool))
    PAPER_MODE: bool = field(default_factory=lambda: get_env("PAPER_MODE", True, bool))
    STREAM_SYMBOLS: List[str] = field(default_factory=lambda: get_env("STREAM_SYMBOLS", "BTCUSDT,ETHUSDT", list))
    STREAM_INTERVAL: str = field(default_factory=lambda: get_env("STREAM_INTERVAL", "1m"))
    DB_PATH: str = field(default_factory=lambda: get_env("DB_PATH", "data/paper_trades.db"))
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: get_env("TELEGRAM_BOT_TOKEN", ""))
    STREAM_GROUP_SIZE: int = field(default_factory=lambda: get_env("STREAM_GROUP_SIZE", 60, int))
    EVALUATOR_WINDOW: int = field(default_factory=lambda: get_env("EVALUATOR_WINDOW", 12, int))
    EVALUATOR_THRESHOLD: float = field(default_factory=lambda: get_env("EVALUATOR_THRESHOLD", 0.25, float))
    RISK_MAX_DAILY_LOSS: float = field(default_factory=lambda: get_env("RISK_MAX_DAILY_LOSS", 0.05, float))

# ----------------------------
# Config instance’ları
# ----------------------------
BINANCE = BinanceConfig()
APIO = APIOConfig()
BOT = BotConfig()
