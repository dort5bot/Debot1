# utils/ap_utils.py - Gelişmiş Versiyon
# - Order Book → VWAP ağırlıklı ve derinlik etkisi
# - Whale / Taker → hacim ve trade boyutu ağırlıklı
# - Altcoin Short Metrics → net IO, momentum ve volatilite etkili
# - Normalize edilmiş skor (0-100)

import asyncio
import numpy as np
import pandas as pd
from utils.binance_api import BinanceClient
from utils.config import CONFIG
from utils.ta_utils import ema, atr

# -------------------------------------------------------------
# Yardımcı Fonksiyonlar
# -------------------------------------------------------------

def _normalize_0_100(series):
    min_val = np.nanmin(series)
    max_val = np.nanmax(series)
    if max_val - min_val == 0:
        return np.zeros_like(series)
    return 100 * (series - min_val) / (max_val - min_val)

# -------------------------------------------------------------
# Order Book Metrikleri
# -------------------------------------------------------------

def order_book_imbalance_vwap(bids: list, asks: list):
    """VWAP ağırlıklı Order Book Imbalance."""
    bid_vol = sum([b[1] for b in bids])
    ask_vol = sum([a[1] for a in asks])
    bid_vwap = sum([b[0]*b[1] for b in bids])/bid_vol if bid_vol else 0
    ask_vwap = sum([a[0]*a[1] for a in asks])/ask_vol if ask_vol else 0
    depth_score = bid_vol - ask_vol
    price_score = ask_vwap - bid_vwap
    return 0.5*depth_score + 0.5*price_score

# -------------------------------------------------------------
# Whale & Taker Metrikleri
# -------------------------------------------------------------

def compute_whale_counts(trades, threshold_usd=None):
    threshold_usd = threshold_usd or CONFIG.WHALE_USD_THRESHOLD
    whale_count = sum(1 for t in trades if float(t["qty"])*float(t["price"]) >= threshold_usd)
    return whale_count

def compute_taker_ratio(trades):
    """Taker buy / sell oranı"""
    buy_volume = sum(float(t["qty"]) for t in trades if t["isBuyerMaker"] is False)
    sell_volume = sum(float(t["qty"]) for t in trades if t["isBuyerMaker"] is True)
    total = buy_volume + sell_volume
    return buy_volume/total if total else 0.5

# -------------------------------------------------------------
# Altcoin Short Metrics
# -------------------------------------------------------------

async def get_altcoin_short_metrics_enhanced(client: BinanceClient, symbol: str):
    """Gelişmiş altcoin kısa dönem metriği"""
    klines = await client.get_klines(symbol, interval="5m", limit=50)
    df = pd.DataFrame(klines, columns=["open_time","open","high","low","close","volume",
                                       "close_time","quote_asset_volume","trades",
                                       "taker_base_vol","taker_quote_vol","ignore"])
    df[["close","high","low","volume"]] = df[["close","high","low","volume"]].astype(float)
    
    # Momentum / Volatilite
    short_mom = df["close"].pct_change().iloc[-1]  # son 5dk
    vol = atr(df, period=14).iloc[-1]              # ATR son değer
    
    # Order Book
    ob = await client.get_order_book(symbol, limit=50)
    obi = order_book_imbalance_vwap(ob["bids"], ob["asks"])
    
    # Trade bazlı
    trades = await client.get_recent_trades(symbol, limit=200)
    whale_score = compute_whale_counts(trades)
    taker_ratio = compute_taker_ratio(trades)
    
    # Bileşik skor (normalize + ağırlık)
    raw_scores = np.array([short_mom, vol, obi, whale_score, taker_ratio])
    norm_scores = _normalize_0_100(raw_scores)
    # Örnek ağırlıklandırma
    weights = np.array([0.3, 0.2, 0.2, 0.2, 0.1])
    composite_score = np.dot(norm_scores, weights)
    
    return {
        "symbol": symbol,
        "composite_score": composite_score,
        "short_momentum": short_mom,
        "volatility": vol,
        "order_book_imbalance": obi,
        "whale_count": whale_score,
        "taker_ratio": taker_ratio
    }

# -------------------------------------------------------------
# Çoklu Altcoin Short Skorları
# -------------------------------------------------------------

async def score_altcoins(client: BinanceClient, symbols: list):
    tasks = [get_altcoin_short_metrics_enhanced(client, s) for s in symbols]
    return await asyncio.gather(*tasks)
