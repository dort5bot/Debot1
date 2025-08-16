# utils/io_utils.py
import asyncio
import logging
from typing import Dict, List

from utils.config import CONFIG
from utils.binance_api import BinanceClient

LOG = logging.getLogger("io_utils")
LOG.addHandler(logging.NullHandler())

# Binance client (tekil instance, paylaşımlı)
binance = BinanceClient()


# -------------------------------------------------------------
# Yardımcı: Trade quote value
# -------------------------------------------------------------
def _trade_quote_value(trade: dict) -> float:
    """
    Trade'in USD karşılığını hesaplar.
    Eğer 'quoteQty' varsa doğrudan kullanır,
    yoksa price * qty üzerinden hesaplar.
    """
    try:
        if "quoteQty" in trade and trade["quoteQty"] is not None:
            return float(trade["quoteQty"])
        return float(trade.get("qty", 0)) * float(trade.get("price", 0))
    except Exception:
        return 0.0


# -------------------------------------------------------------
# Market In/Out
# -------------------------------------------------------------
async def market_inout(limit_per_symbol: int = None) -> Dict[str, Dict[str, float]]:
    """
    Basit market in/out hesaplaması:
      - Her sembol için son N trade'e bakar,
      - isBuyerMaker == False => taker was buyer (buy taker volume)
      - isBuyerMaker == True  => taker was seller (sell taker volume)

    Döner:
      { "BTCUSDT": {"buy": 12345.0, "sell": 54321.0}, ... }
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT

    tickers = await binance.get_all_24h_tickers()
    usdt_ticks = [t for t in tickers if t.get("symbol", "").endswith("USDT")]
    usdt_ticks.sort(key=lambda x: float(x.get("quoteVolume", 0.0)), reverse=True)

    symbols = CONFIG.BINANCE.TOP_SYMBOLS_FOR_IO or [
        t["symbol"] for t in usdt_ticks[:50]
    ]

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, Dict[str, float]] = {}

    async def _process(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy, sell = 0.0, 0.0
            for tr in trades:
                qv = _trade_quote_value(tr)
                if tr.get("isBuyerMaker", False):
                    sell += qv
                else:
                    buy += qv
            out[sym] = {"buy": buy, "sell": sell}

    await asyncio.gather(*[_process(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Whale Trade Counts
# -------------------------------------------------------------
async def compute_whale_counts(
    symbols: List[str],
    limit_per_symbol: int = None,
    threshold_usd: float = None
) -> Dict[str, Dict[str, int]]:
    """
    Her sembol için whale (tek trade > threshold_usd) alım/satım sayısını döndürür.

    Döner:
      { "BTCUSDT": {"whale_buy_count": 2, "whale_sell_count": 5}, ... }
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT
    threshold_usd = threshold_usd or CONFIG.BINANCE.WHALE_USD_THRESHOLD

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, Dict[str, int]] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            wb, ws = 0, 0
            for tr in trades:
                qv = _trade_quote_value(tr)
                if qv >= threshold_usd:
                    if not tr.get("isBuyerMaker", False):
                        wb += 1
                    else:
                        ws += 1
            out[sym] = {"whale_buy_count": wb, "whale_sell_count": ws}

    await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Taker Ratio
# -------------------------------------------------------------
async def compute_taker_ratio(
    symbols: List[str],
    limit_per_symbol: int = None
) -> Dict[str, float]:
    """
    Her sembol için taker buy ratio hesaplar:
      taker_buy_volume / (taker_buy + taker_sell)

    Döner:
      { "BTCUSDT": 0.62, ... } (0..1 arası)
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, float] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy, sell = 0.0, 0.0
            for tr in trades:
                qv = _trade_quote_value(tr)
                if not tr.get("isBuyerMaker", False):
                    buy += qv
                else:
                    sell += qv
            denom = buy + sell
            out[sym] = (buy / denom) if denom > 0 else 0.5

    await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
    return out
