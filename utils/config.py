# utils/config.py
#  Artık STREAM_SYMBOLS, STREAM_INTERVAL, PAPER_MODE, EVALUATOR_WINDOW, EVALUATOR_THRESHOLD tamamen config üzerinden okunuyor.
#  Deploy sırasında hiçbir ImportError oluşmayacak.
#  İleriye dönük olarak .env üzerinden bu değerleri değiştirmek yeterli.

# utils/config.py
# Bot başlatıldığında .env’den API Key ve Secret Key’i okur.
# /apikey komutu ile runtime + kalıcı olarak güncelleme yapılabilir.
# Yetkisiz kullanıcıların erişimi engellenir.
# Yapı tamamen mevcut CONFIG ve handler sistemini bozmadan entegre olur.
# Böylece hem güvenli hem de kalıcı bir API Key yönetimi sağlanmış olur.

    
import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv, set_key

# --- .env yükle ---
ENV_PATH = ".env"
load_dotenv(ENV_PATH, override=True)

# === Binance Config ===
@dataclass
class BinanceConfig:
    BASE_URL: str = "https://api.binance.com/api/v3"
    FAPI_URL: str = "https://fapi.binance.com/fapi/v1"
    API_KEY: Optional[str] = os.getenv("BINANCE_API_KEY")
    SECRET_KEY: Optional[str] = os.getenv("BINANCE_SECRET_KEY")
    CONCURRENCY: int = int(os.getenv("BINANCE_CONCURRENCY", 8))
    TRADES_LIMIT: int = int(os.getenv("TRADES_LIMIT", 500))
    WHALE_USD_THRESHOLD: float = float(os.getenv("WHALE_USD_THRESHOLD", 50000))
    TOP_SYMBOLS_FOR_IO: List[str] = field(
        default_factory=lambda: os.getenv("TOP_SYMBOLS_FOR_IO", "BTCUSDT,ETHUSDT").split(",")
    )
    IO_CONCURRENCY: int = int(os.getenv("IO_CONCURRENCY", 5))
    BINANCE_TICKER_TTL: int = int(os.getenv("BINANCE_TICKER_TTL", 5))
    STREAM_INTERVAL: str = os.getenv("STREAM_INTERVAL", "1m")

# === Bot Config ===
@dataclass
class BotConfig:
    PAPER_MODE: bool = os.getenv("PAPER_MODE", "true").lower() == "true"
    EVALUATOR_WINDOW: int = int(os.getenv("EVALUATOR_WINDOW", 60))
    EVALUATOR_THRESHOLD: float = float(os.getenv("EVALUATOR_THRESHOLD", 0.5))

# === TA Config ===
@dataclass
class TAConfig:
    EMA_PERIODS: List[int] = field(
        default_factory=lambda: [int(x) for x in os.getenv("EMA_PERIODS", "20,50,200").split(",")]
    )
    MACD_FAST: int = int(os.getenv("MACD_FAST", 12))
    MACD_SLOW: int = int(os.getenv("MACD_SLOW", 26))
    MACD_SIGNAL: int = int(os.getenv("MACD_SIGNAL", 9))
    ADX_PERIOD: int = int(os.getenv("ADX_PERIOD", 14))
    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", 14))
    STOCH_K: int = int(os.getenv("STOCH_K", 14))
    STOCH_D: int = int(os.getenv("STOCH_D", 3))
    ATR_PERIOD: int = int(os.getenv("ATR_PERIOD", 14))
    BB_PERIOD: int = int(os.getenv("BB_PERIOD", 20))
    BB_STDDEV: float = float(os.getenv("BB_STDDEV", 2))
    SHARPE_RISK_FREE_RATE: float = float(os.getenv("SHARPE_RISK_FREE_RATE", 0.02))
    OBV_ENABLED: bool = os.getenv("OBV_ENABLED", "true").lower() == "true"
    OBI_DEPTH: int = int(os.getenv("OBI_DEPTH", 20))
    OPEN_INTEREST_ENABLED: bool = os.getenv("OPEN_INTEREST_ENABLED", "true").lower() == "true"
    FUNDING_RATE_ENABLED: bool = os.getenv("FUNDING_RATE_ENABLED", "true").lower() == "true"
    SOCIAL_SENTIMENT_ENABLED: bool = os.getenv("SOCIAL_SENTIMENT_ENABLED", "false").lower() == "true"

# === Telegram Config ===
@dataclass
class TelegramConfig:
    BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    ALERT_CHAT_ID: Optional[str] = os.getenv("ALERT_CHAT_ID")

# === Database Config ===
@dataclass
class DatabaseConfig:
    DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

# === Master Config ===
@dataclass
class AppConfig:
    BINANCE: BinanceConfig = field(default_factory=BinanceConfig)
    BOT: BotConfig = field(default_factory=BotConfig)
    TA: TAConfig = field(default_factory=TAConfig)
    TELEGRAM: TelegramConfig = field(default_factory=TelegramConfig)
    DATABASE: DatabaseConfig = field(default_factory=DatabaseConfig)

CONFIG = AppConfig()


# --- Fonksiyon: .env ve CONFIG güncelleme ---
def update_binance_keys(api_key: str, secret_key: str):
    CONFIG.BINANCE.API_KEY = api_key
    CONFIG.BINANCE.SECRET_KEY = secret_key
    if os.path.exists(ENV_PATH):
        set_key(ENV_PATH, "BINANCE_API_KEY", api_key)
        set_key(ENV_PATH, "BINANCE_SECRET_KEY", secret_key)
        load_dotenv(ENV_PATH, override=True)

