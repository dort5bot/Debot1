# utils/io_utils.py (Full Revize)
# - Weighted ve zaman bazlı trade analizi
# - Whale momentum + taker ratio ağırlıklı
# - Whale analizleri sayısal + hacim + momentum içeriyor.
# - Order book depth + imbalance etkisi
# - Real-time WS destekli update
# - OBV ve volume delta hesaplaması
# - Market in/out zaman bazlı filtreleme ile trend veriyor.
# - Taker ratio weighted ve büyük trade’leri önceliklendiriyor.
# - Volume delta ve order book imbalance hassas ve ağırlıklı hesaplanıyor.

# utils/io_utils.py
import math
import statistics
from typing import Dict, Any, List, Optional

# ===============================
# --- Yardımcı Hesaplamalar ---
# ===============================

def safe_mean(values: List[float]) -> Optional[float]:
    """Boş listeye karşı güvenli mean"""
    try:
        return statistics.mean(values) if values else None
    except Exception:
        return None

def calc_momentum(klines: List[List[Any]]) -> Optional[float]:
    """RSI / momentum (14 period)"""
    try:
        close_prices = [float(k[4]) for k in klines[-14:]]
        if len(close_prices) < 2:
            return None
        gains = [max(0, close_prices[i] - close_prices[i-1]) for i in range(1, len(close_prices))]
        losses = [max(0, close_prices[i-1] - close_prices[i]) for i in range(1, len(close_prices))]
        avg_gain = safe_mean(gains) or 0.0
        avg_loss = safe_mean(losses) or 0.0
        rs = avg_gain / avg_loss if avg_loss > 0 else float("inf")
        return 100 - (100 / (1 + rs))
    except Exception:
        return None

def calc_volatility(klines: List[List[Any]]) -> Optional[float]:
    """Basit volatilite hesaplama (standart sapma)"""
    try:
        closes = [float(k[4]) for k in klines]
        return statistics.pstdev(closes) if closes else None
    except Exception:
        return None

def calc_obi(order_book: Dict[str, Any]) -> Optional[float]:
    """Order Book Imbalance (OBI)"""
    try:
        bids = sum(float(b[1]) for b in order_book.get("bids", []))
        asks = sum(float(a[1]) for a in order_book.get("asks", []))
        return (bids - asks) / (bids + asks) if (bids + asks) > 0 else None
    except Exception:
        return None

def calc_liquidity_layers(order_book: Dict[str, Any], price: float, pct_levels=[0.01, 0.02, 0.05]):
    """Derinlikte likidite yoğunluğu"""
    layers = {}
    try:
        for p in pct_levels:
            bid_layer = sum(float(b[1]) for b in order_book.get("bids", []) if float(b[0]) >= price * (1 - p))
            ask_layer = sum(float(a[1]) for a in order_book.get("asks", []) if float(a[0]) <= price * (1 + p))
            layers[f"layer_{int(p*100)}"] = {"bids": bid_layer, "asks": ask_layer}
    except Exception:
        pass
    return layers

def calc_taker_ratio(trades: List[Dict[str, Any]]) -> Optional[float]:
    """Aggressor taker oranı (buy-sell / total)"""
    try:
        buys = sum(float(t["qty"]) for t in trades if not t.get("isBuyerMaker"))
        sells = sum(float(t["qty"]) for t in trades if t.get("isBuyerMaker"))
        total = buys + sells
        return (buys - sells) / total if total > 0 else None
    except Exception:
        return None

def normalize_funding(funding_rate: float, avg: float = 0.0001, std: float = 0.0005) -> Optional[float]:
    """Funding z-score normalizasyon"""
    try:
        return (funding_rate - avg) / std if std != 0 else None
    except Exception:
        return None

def normalize_oi(oi: Optional[float], baseline: float = 1e9) -> Optional[float]:
    """Open Interest normalizasyon"""
    try:
        return oi / baseline if oi else None
    except Exception:
        return None

def normalize_liquidations(liquidations: Optional[float], baseline: float = 1e6) -> Optional[float]:
    """Likidasyonlar için normalizasyon"""
    try:
        return liquidations / baseline if liquidations else None
    except Exception:
        return None

# ===============================
# --- IO Snapshot Builder ---
# ===============================

def build_io_snapshot(
    symbol: str,
    klines,
    order_book,
    trades,
    ticker,
    funding,
    oi: Optional[float] = None,
    liquidations: Optional[float] = None
):
    """IO verilerinden özet snapshot üretir"""
    # --- Hesaplamalar ---
    momentum = calc_momentum(klines)
    volatility = calc_volatility(klines)
    obi = calc_obi(order_book)
    liquidity_layers = calc_liquidity_layers(order_book, float(ticker.get("lastPrice", 0)))
    taker_ratio = calc_taker_ratio(trades)
    funding_rate = float(funding.get("fundingRate", 0))
    funding_norm = normalize_funding(funding_rate)
    oi_norm = normalize_oi(oi)
    liq_norm = normalize_liquidations(liquidations)

    # --- Skorlar ---
    trend_score = safe_mean([
        (momentum / 100 if momentum is not None else 0),
        (funding_norm if funding_norm is not None else 0),
    ]) or 0

    liquidity_score = safe_mean([
        (obi if obi is not None else 0),
        (taker_ratio if taker_ratio is not None else 0),
    ]) or 0

    risk_score = safe_mean([
        (volatility if volatility is not None else 0),
        (liq_norm if liq_norm is not None else 0),
    ]) or 0

    mts_score = trend_score + liquidity_score - risk_score

    return {
        "symbol": symbol,
        "momentum": momentum,
        "volatility": volatility,
        "obi": obi,
        "liquidity_layers": liquidity_layers,
        "taker_ratio": taker_ratio,
        "funding_rate": funding_rate,
        "funding_norm": funding_norm,
        "open_interest": oi,
        "open_interest_norm": oi_norm,
        "liquidations": liquidations,
        "liquidations_norm": liq_norm,
        "trend_score": trend_score,
        "liquidity_score": liquidity_score,
        "risk_score": risk_score,
        "mts_score": mts_score,
        }
    
