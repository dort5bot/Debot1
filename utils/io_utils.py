# utils/io_utils.py
import asyncio
import os
import logging
from typing import Dict, List
from decimal import Decimal
from utils import binance_api

LOG = logging.getLogger("io_utils")
LOG.addHandler(logging.NullHandler())

# Ayarlar (env ile de kontrol edilebilir)
WHALE_USD_THRESHOLD = float(os.getenv("WHALE_USD_THRESHOLD", "100000"))  # 100k USD üzeri tek trade = balina
TRADES_LIMIT = int(os.getenv("IO_TRADES_LIMIT", "500"))  # son kaç trade incelensin
TOP_SYMBOLS_FOR_IO = int(os.getenv("TOP_SYMBOLS_FOR_IO", "120"))  # kaç top hacim sembolü incelensin
CONCURRENCY = int(os.getenv("IO_CONCURRENCY", "8"))

def _trade_quote_value(trade: dict) -> float:
    # Eğer quoteQty varsa kullan; yoksa price*qty
    try:
        if "quoteQty" in trade and trade["quoteQty"] is not None:
            return float(trade["quoteQty"])
        return float(trade.get("qty", 0)) * float(trade.get("price", 0))
    except Exception:
        return 0.0

async def market_inout(limit_per_symbol: int = TRADES_LIMIT) -> Dict[str, Dict[str, float]]:
    """
    Basit market in/out hesaplaması:
      - Her sembol için son N trade'e bakar,
      - isBuyerMaker == False => taker was buyer (buy taker volume)
      - isBuyerMaker == True  => taker was seller (sell taker volume)
    Döner: { "BTCUSDT": {"buy": 12345.0, "sell": 54321.0}, ... }
    """
    tickers = await binance_api.get_all_24h_tickers()
    # Öncelikle USDT quote'lu ve trading olanları hacme göre seç
    usdt_ticks = [t for t in tickers if t.get("symbol", "").endswith("USDT")]
    usdt_ticks.sort(key=lambda x: float(x.get("quoteVolume", 0.0)), reverse=True)
    symbols = [t["symbol"] for t in usdt_ticks[:TOP_SYMBOLS_FOR_IO]]

    sem = asyncio.Semaphore(CONCURRENCY)
    out: Dict[str, Dict[str, float]] = {}

    async def _process(sym: str):
        async with sem:
            trades = await binance_api.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy = 0.0
            sell = 0.0
            for tr in trades:
                qv = _trade_quote_value(tr)
                # isBuyerMaker True => buyer is maker, taker is seller
                is_buyer_maker = tr.get("isBuyerMaker", False)
                if is_buyer_maker:
                    # taker was seller
                    sell += qv
                else:
                    buy += qv
            out[sym] = {"buy": buy, "sell": sell}
    tasks = [_process(s) for s in symbols]
    await asyncio.gather(*tasks, return_exceptions=True)
    return out

async def compute_whale_counts(symbols: List[str], limit_per_symbol: int = TRADES_LIMIT, threshold_usd: float = WHALE_USD_THRESHOLD) -> Dict[str, Dict[str, int]]:
    """
    Her sembol için whale (tek trade > threshold_usd) alım/satım sayısını döndürür.
    Döner: { "BTCUSDT": {"whale_buy_count": 2, "whale_sell_count": 5}, ... }
    """
    sem = asyncio.Semaphore(CONCURRENCY)
    out: Dict[str, Dict[str, int]] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance_api.get_recent_trades(sym, limit=limit_per_symbol) or []
            wb = 0
            ws = 0
            for tr in trades:
                qv = _trade_quote_value(tr)
                if qv >= threshold_usd:
                    # isBuyerMaker False => taker buy
                    if not tr.get("isBuyerMaker", False):
                        wb += 1
                    else:
                        ws += 1
            out[sym] = {"whale_buy_count": wb, "whale_sell_count": ws}
    tasks = [_one(s) for s in symbols]
    await asyncio.gather(*tasks, return_exceptions=True)
    return out

async def compute_taker_ratio(symbols: List[str], limit_per_symbol: int = TRADES_LIMIT) -> Dict[str, float]:
    """
    Her sembol için taker buy ratio = taker_buy_volume / (taker_buy + taker_sell)
    Döner: { "BTCUSDT": 0.62, ... } (0..1 arası)
    """
    sem = asyncio.Semaphore(CONCURRENCY)
    out: Dict[str, float] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance_api.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy = 0.0
            sell = 0.0
            for tr in trades:
                qv = _trade_quote_value(tr)
                if not tr.get("isBuyerMaker", False):
                    buy += qv
                else:
                    sell += qv
            denom = buy + sell
            out[sym] = (buy / denom) if denom > 0 else 0.5
    tasks = [_one(s) for s in symbols]
    await asyncio.gather(*tasks, return_exceptions=True)
    return out
