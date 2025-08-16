# # utils/config.py

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


# === Binance Config ===
@dataclass
class BinanceConfig:
    BASE_URL: str = "https://api.binance.com/api/v3"
    FAPI_URL: str = "https://fapi.binance.com/fapi/v1"
    CONCURRENCY: int = int(os.getenv("BINANCE_CONCURRENCY", 8))
    TRADES_LIMIT: int = int(os.getenv("TRADES_LIMIT", 500))
    WHALE_USD_THRESHOLD: float = float(os.getenv("WHALE_USD_THRESHOLD", 50000))
    TOP_SYMBOLS_FOR_IO: List[str] = field(
        default_factory=lambda: os.getenv("TOP_SYMBOLS_FOR_IO", "BTCUSDT,ETHUSDT").split(",")
    )
    IO_CONCURRENCY: int = int(os.getenv("IO_CONCURRENCY", 5))
    BINANCE_TICKER_TTL: int = int(os.getenv("BINANCE_TICKER_TTL", 5))


# === TA (Technical Analysis) Config ===
@dataclass
class TAConfig:
    # --- Trend ---
    EMA_PERIODS: List[int] = field(
        default_factory=lambda: [int(x) for x in os.getenv("EMA_PERIODS", "20,50,200").split(",")]
    )
    MACD_FAST: int = int(os.getenv("MACD_FAST", 12))
    MACD_SLOW: int = int(os.getenv("MACD_SLOW", 26))
    MACD_SIGNAL: int = int(os.getenv("MACD_SIGNAL", 9))
    ADX_PERIOD: int = int(os.getenv("ADX_PERIOD", 14))

    # --- Momentum ---
    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", 14))
    STOCH_K: int = int(os.getenv("STOCH_K", 14))
    STOCH_D: int = int(os.getenv("STOCH_D", 3))

    # --- Volatilite & Risk ---
    ATR_PERIOD: int = int(os.getenv("ATR_PERIOD", 14))
    BB_PERIOD: int = int(os.getenv("BB_PERIOD", 20))
    BB_STDDEV: float = float(os.getenv("BB_STDDEV", 2))
    SHARPE_RISK_FREE_RATE: float = float(os.getenv("SHARPE_RISK_FREE_RATE", 0.02))  # %2 varsayılan

    # --- Hacim & Likidite ---
    OBV_ENABLED: bool = os.getenv("OBV_ENABLED", "true").lower() == "true"
    OBI_DEPTH: int = int(os.getenv("OBI_DEPTH", 20))
    OPEN_INTEREST_ENABLED: bool = os.getenv("OPEN_INTEREST_ENABLED", "true").lower() == "true"

    # --- Sentiment ---
    FUNDING_RATE_ENABLED: bool = os.getenv("FUNDING_RATE_ENABLED", "true").lower() == "true"
    SOCIAL_SENTIMENT_ENABLED: bool = os.getenv("SOCIAL_SENTIMENT_ENABLED", "false").lower() == "true"


# === Master Config ===
@dataclass
class AppConfig:
    BINANCE: BinanceConfig = BinanceConfig()
    TA: TAConfig = TAConfig()
    # İleride: TELEGRAM, DATABASE vb. eklenebilir


CONFIG = AppConfig()
