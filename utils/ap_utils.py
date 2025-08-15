#ap_utils.py
#
#
#
#
import asyncio
import math
from typing import Dict, List, Optional
from utils import binance_api

# io_utils opsiyonel olabilir. Yoksa net_io = 0 kabul edilir.
try:
    from utils import io_utils  # market_inout() -> { "BTCUSDT": {"buy":x,"sell":y}, ... }
except Exception:
    io_utils = None  # type: ignore

STABLE_QUOTES = {"USDT", "USDC", "BUSD", "FDUSD"}

# ---- Yardımcılar ------------------------------------------------------------
def _is_stable_quote(sym: str) -> Optional[str]:
    for q in STABLE_QUOTES:
        if sym.endswith(q):
            return q
    return None

def _is_leveraged_token(base: str) -> bool:
    # UP/DOWN, BULL/BEAR, 2L/3L/5L/2S/3S/5S gibi ürünleri hariç tut
    bad_suffixes = ("UP", "DOWN", "BULL", "BEAR", "2L", "3L", "5L", "2S", "3S", "5S")
    return base.endswith(bad_suffixes)

def _decimal_tr(value: float) -> str:
    # TR formatı: 12.3 -> "12,3"
    return f"{value:.1f}".replace(".", ",")

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _normalize_0_100(x: float, xmin: float, xmax: float) -> float:
    # Lineer normalizasyon
    if xmax == xmin:
        return 50.0
    return _clamp((x - xmin) / (xmax - xmin) * 100.0, 0.0, 100.0)

async def _get_market_io() -> Dict[str, Dict[str, float]]:
    if io_utils and hasattr(io_utils, "market_inout"):
        try:
            return await io_utils.market_inout()
        except Exception:
            return {}
    return {}

# ---- Metrikler --------------------------------------------------------------
async def get_btc_dominance() -> float:
    """
    BTC Dominance (spot, stable-quoted piyasalar üzerinden):
    BTCUSDT hacmi / (stable-quoted toplam hacim)
    """
    tickers = await binance_api.get_all_24h_tickers()
    total_vol = 0.0
    btc_vol = 0.0

    for t in tickers:
        sym = t.get("symbol", "")
        quote = _is_stable_quote(sym)
        if not quote:
            continue
        base = sym[:-len(quote)]
        if base in STABLE_QUOTES or _is_leveraged_token(base):
            continue  # stable/stable veya LT tokenları atla

        qvol = float(t.get("quoteVolume", 0.0))
        total_vol += qvol
        if sym == "BTCUSDT":
            btc_vol += qvol

    return (btc_vol / total_vol) * 100.0 if total_vol > 0 else 0.0

async def get_altcoin_short_metrics() -> Dict[str, float]:
    """
    Altcoin kısa vade metrikleri (24h):
      - Hacim ağırlıklı fiyat değişimi (%)
      - Net in/out (USD)
    BTC ve stable/stable hariç, yalnızca stable-quoted pariteler.
    """
    tickers = await binance_api.get_all_24h_tickers()
    market_io = await _get_market_io()

    sum_vol = 0.0
    sum_wchg = 0.0  # change * vol
    net_io = 0.0

    for t in tickers:
        sym = t.get("symbol", "")
        if not sym or sym.startswith("BTC"):
            continue
        quote = _is_stable_quote(sym)
        if not quote:
            continue
        base = sym[:-len(quote)]
        if base in STABLE_QUOTES or _is_leveraged_token(base):
            continue

        qvol = float(t.get("quoteVolume", 0.0))
        chg = float(t.get("priceChangePercent", 0.0))
        sum_vol += qvol
        sum_wchg += chg * qvol

        if sym in market_io:
            buy = float(market_io[sym].get("buy", 0.0))
            sell = float(market_io[sym].get("sell", 0.0))
            net_io += (buy - sell)

    wchg = (sum_wchg / sum_vol) if sum_vol > 0 else 0.0
    return {"price_change": wchg, "net_io": net_io, "volume": sum_vol}

async def get_btc_short_metrics() -> Dict[str, float]:
    """
    BTC kısa vade (24h) değişimi ve net in/out.
    """
    t = await binance_api.get_24h_ticker("BTCUSDT")
    market_io = await _get_market_io()

    chg = float(t.get("priceChangePercent", 0.0)) if t else 0.0
    qvol = float(t.get("quoteVolume", 0.0)) if t else 0.0
    net_io = 0.0
    if "BTCUSDT" in market_io:
        buy = float(market_io["BTCUSDT"].get("buy", 0.0))
        sell = float(market_io["BTCUSDT"].get("sell", 0.0))
        net_io = buy - sell

    return {"price_change": chg, "net_io": net_io, "volume": qvol}

async def get_long_term_breadth(top_n: int = 30) -> float:
    """
    Uzun vade güç: En yüksek hacimli TOP-N USDT alt arasında son 30 günlük performans >0 olanların oranı (0–100).
    Kline isteklerini sınırlı concurrency ile yapar (429 riskini azaltır).
    """
    tickers = await binance_api.get_all_24h_tickers()
    # USDT altları hacme göre sırala
    alts: List[tuple[str, float]] = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT") or sym == "BTCUSDT":
            continue
        base = sym[:-4]
        if base in STABLE_QUOTES or _is_leveraged_token(base):
            continue
        qvol = float(t.get("quoteVolume", 0.0))
        alts.append((sym, qvol))
    alts.sort(key=lambda x: x[1], reverse=True)
    symbols = [s for s, _ in alts[:max(10, min(top_n, 80))]]

    # 31 günlük 1D klines (dünkü kapanışa kadar)
    klines_map = await binance_api.get_multiple_klines(symbols, interval="1d", limit=31, concurrency=6)

    winners = 0
    total = 0
    for sym in symbols:
        kl = klines_map.get(sym)
        if not kl or len(kl) < 2:
            continue
        # kline: [openTime, open, high, low, close, ...]
        close_0 = float(kl[-1][4])  # son kapanış
        close_30 = float(kl[0][4])  # 30 gün önceki kapanış
        if close_30 > 0:
            pct = (close_0 - close_30) / close_30 * 100.0
            winners += 1 if pct > 0 else 0
            total += 1

    if total == 0:
        return 50.0
    return (winners / total) * 100.0

# ---- 0–100 Skorlar ----------------------------------------------------------
def score_alt_vs_btc_short(alt_chg: float, btc_chg: float, btc_dom: float) -> float:
    """
    Altların BTC'ye karşı kısa vade gücü:
      - Fiyat farkı (alt% - btc%) -10..+10 -> 0..100
      - BTC dominance düşükse küçük bir bonus.
    """
    diff = alt_chg - btc_chg
    base = _normalize_0_100(diff, -8.0, 8.0)  # tipik bant
    bonus = _normalize_0_100(60 - btc_dom, 0, 60) * 0.1  # dom düşükse +max 10 puan
    return _clamp(base + bonus, 0, 100)

def score_alt_short(alt_chg: float, alt_net_io: float) -> float:
    """
    Altların kısa vade genel gücü:
      - Fiyat değişimi: -6..+6 -> 0..100
      - Net IO: -500M..+500M -> 0..100, %40 ağırlık
    """
    s_chg = _normalize_0_100(alt_chg, -6.0, 6.0)
    s_io = _normalize_0_100(alt_net_io, -500_000_000.0, 500_000_000.0)
    return _clamp(0.6 * s_chg + 0.4 * s_io, 0, 100)

def score_long_term(breadth_0_100: float) -> float:
    """
    Uzun vade güç: doğrudan breadth yüzdesi (top-n pozitif eğilim oranı).
    """
    return _clamp(breadth_0_100, 0, 100)

# ---- Ana koleksiyon ---------------------------------------------------------
async def collect_ap_scores() -> Dict[str, float]:
    btc_dom, alt_short, btc_short = await asyncio.gather(
        get_btc_dominance(),
        get_altcoin_short_metrics(),
        get_btc_short_metrics(),
    )
    breadth = await get_long_term_breadth(top_n=30)

    s1 = score_alt_vs_btc_short(alt_short["price_change"], btc_short["price_change"], btc_dom)
    s2 = score_alt_short(alt_short["price_change"], alt_short["net_io"])
    s3 = score_long_term(breadth)

    return {
        "alt_vs_btc_short": s1,
        "alt_short": s2,
        "coins_long": s3,
    }

# ---- Dışa açık: rapor formatına yardımcı -----------------------------------
async def build_ap_report_lines() -> List[str]:
    scores = await collect_ap_scores()
    return [
        f"Altların Kısa Vadede Btc'ye Karşı Gücü(0-100): {_decimal_tr(scores['alt_vs_btc_short'])}",
        f"Altların Kısa Vadede Gücü(0-100): {_decimal_tr(scores['alt_short'])}",
        f"Coinlerin Uzun Vadede Gücü(0-100): {_decimal_tr(scores['coins_long'])}",
]
