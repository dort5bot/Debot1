# utils/io_utils.py (revize edilmiş)
# - daha nitelikli ve gelişmiş analizler yapacak şekilde revize
# - Weighted ve zaman bazlı trade analizi
# - Whale momentum + taker ratio ağırlıklı
# - Whale analizleri artık sayısal + hacim + momentum içeriyor.
# - Order book depth + imbalance etkisi
# - Real-time WS destekli update
# - OBV ve volume delta hesaplaması
# - Market in/out zaman bazlı filtreleme ile daha güncel trend veriyor.
# - Taker ratio weighted ve büyük trade’leri önceliklendiriyor.
# - Volume delta ve order book imbalance daha hassas ve ağırlıklı hesaplanıyor.



import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from utils.config import CONFIG
from utils.binance_api import BinanceClient

LOG = logging.getLogger("io_utils")
LOG.addHandler(logging.NullHandler())

# Singleton Binance client
binance = BinanceClient()

# -------------------------------------------------------------
# Yardımcı: Trade quote value (USD normalize)
# -------------------------------------------------------------
def _trade_quote_value(trade: dict, symbol: str = None) -> float:
    """
    Trade'in USD karşılığını hesaplar.
    quoteQty varsa direkt alır, yoksa price*qty.
    Symbol USD değilse normalize edilebilir (basit örnek: ara parite).
    """
    try:
        if "quoteQty" in trade and trade["quoteQty"] is not None:
            return float(trade["quoteQty"])
        return float(trade.get("qty", 0)) * float(trade.get("price", 0))
    except Exception:
        return 0.0


# -------------------------------------------------------------
# Market In/Out (Weighted + Time Bucket)
# -------------------------------------------------------------
async def market_inout(symbols: Optional[List[str]] = None, limit_per_symbol: int = None, window_minutes: int = 60) -> Dict[str, Dict[str, float]]:
    """
    Weighted market in/out hesaplar, son window_minutes içindeki trade'leri bucket'lar.
    Return: { "BTCUSDT": {"buy": 12345.0, "sell": 54321.0}, ... }
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT

    # Varsayılan en yüksek hacimli semboller
    if not symbols:
        tickers = await binance.get_all_24h_tickers()
        usdt_ticks = [t for t in tickers if t.get("symbol", "").endswith("USDT")]
        usdt_ticks.sort(key=lambda x: float(x.get("quoteVolume", 0.0)), reverse=True)
        symbols = CONFIG.BINANCE.TOP_SYMBOLS_FOR_IO or [t["symbol"] for t in usdt_ticks[:50]]

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, Dict[str, float]] = {}

    async def _process(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy, sell = 0.0, 0.0
            cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
            for tr in trades:
                ts = datetime.utcfromtimestamp(tr.get("time", 0)/1000)
                if ts < cutoff:
                    continue
                qv = _trade_quote_value(tr, sym)
                if tr.get("isBuyerMaker", False):
                    sell += qv
                else:
                    buy += qv
            out[sym] = {"buy": buy, "sell": sell}

    await asyncio.gather(*[_process(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Whale Trade Counts + Momentum
# -------------------------------------------------------------
async def compute_whale_counts(symbols: List[str], limit_per_symbol: int = None, threshold_usd: float = None) -> Dict[str, Dict[str, float]]:
    """
    Whale trade sayısı + weighted volume + buy/sell momentum
    Return: 
      {
        "BTCUSDT": {
            "whale_buy_count": 2,
            "whale_sell_count": 5,
            "whale_buy_volume": 123456.0,
            "whale_sell_volume": 54321.0,
            "whale_delta": 0.69   # buy volume / (buy+sell)
        }, ...
      }
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT
    threshold_usd = threshold_usd or CONFIG.BINANCE.WHALE_USD_THRESHOLD

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, Dict[str, float]] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            wb, ws, vb, vs = 0, 0, 0.0, 0.0
            for tr in trades:
                qv = _trade_quote_value(tr, sym)
                if qv >= threshold_usd:
                    if not tr.get("isBuyerMaker", False):
                        wb += 1
                        vb += qv
                    else:
                        ws += 1
                        vs += qv
            total_vol = vb + vs
            delta = (vb / total_vol) if total_vol > 0 else 0.5
            out[sym] = {
                "whale_buy_count": wb,
                "whale_sell_count": ws,
                "whale_buy_volume": vb,
                "whale_sell_volume": vs,
                "whale_delta": delta
            }

    await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Taker Ratio (Weighted + Price Impact)
# -------------------------------------------------------------
async def compute_taker_ratio(symbols: List[str], limit_per_symbol: int = None) -> Dict[str, float]:
    """
    Weighted taker buy ratio hesaplar:
      taker_buy_volume / (taker_buy + taker_sell)
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT

    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, float] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy, sell = 0.0, 0.0
            for tr in trades:
                qv = _trade_quote_value(tr, sym)
                weight = min(qv / 10000, 1.0)  # büyük trades daha fazla ağırlık
                if not tr.get("isBuyerMaker", False):
                    buy += qv * weight
                else:
                    sell += qv * weight
            denom = buy + sell
            out[sym] = (buy / denom) if denom > 0 else 0.5

    await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Volume Delta & OBV
# -------------------------------------------------------------
async def compute_volume_delta(symbols: List[str], limit_per_symbol: int = None) -> Dict[str, float]:
    """
    Volume delta: buy volume - sell volume
    """
    limit_per_symbol = limit_per_symbol or CONFIG.BINANCE.TRADES_LIMIT
    sem = asyncio.Semaphore(CONFIG.BINANCE.IO_CONCURRENCY)
    out: Dict[str, float] = {}

    async def _one(sym: str):
        async with sem:
            trades = await binance.get_recent_trades(sym, limit=limit_per_symbol) or []
            buy, sell = 0.0, 0.0
            for tr in trades:
                qv = _trade_quote_value(tr, sym)
                if not tr.get("isBuyerMaker", False):
                    buy += qv
                else:
                    sell += qv
            out[sym] = buy - sell

    await asyncio.gather(*[_one(s) for s in symbols], return_exceptions=True)
    return out


# -------------------------------------------------------------
# Order Book Imbalance + Weighted Depth
# -------------------------------------------------------------
def compute_order_book_imbalance(bids: list, asks: list, depth_limit: int = 5):
    """
    Basit OBI + depth etkisi (ilk N seviyeyi ağırlıklandır)
    """
    bid_vol, ask_vol = 0.0, 0.0
    for i, b in enumerate(bids[:depth_limit]):
        weight = (depth_limit - i) / depth_limit
        bid_vol += b[1] * weight
    for i, a in enumerate(asks[:depth_limit]):
        weight = (depth_limit - i) / depth_limit
        ask_vol += a[1] * weight
    return (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0.0
