# utils/ap_utils.py
import asyncio
import math
from typing import Dict, List, Optional
from utils import binance_api
from utils import io_utils  # yeni

STABLE_QUOTES = {"USDT", "USDC", "BUSD", "FDUSD"}

# --- Yardımcılar aynı (öncekiler) ---
def _is_stable_quote(sym: str) -> Optional[str]:
    for q in STABLE_QUOTES:
        if sym.endswith(q):
            return q
    return None

def _is_leveraged_token(base: str) -> bool:
    bad_suffixes = ("UP", "DOWN", "BULL", "BEAR", "2L", "3L", "5L", "2S", "3S", "5S")
    return base.endswith(bad_suffixes)

def _decimal_tr(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _normalize_0_100(x: float, xmin: float, xmax: float) -> float:
    if xmax == xmin:
        return 50.0
    return _clamp((x - xmin) / (xmax - xmin) * 100.0, 0.0, 100.0)

async def compute_order_book_imbalance(symbol: str, top_n: int = 10) -> float:
    """
    Order book imbalance (top_n seviyede):
      imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) -> -1..1
      dönüştürülür -> 0..100
    """
    ob = await binance_api.get_order_book(symbol, limit=top_n)
    if not ob:
        return 50.0
    bids = ob.get("bids", [])[:top_n]
    asks = ob.get("asks", [])[:top_n]
    bid_vol = sum(float(b[1]) * float(b[0]) for b in bids)  # qty * price
    ask_vol = sum(float(a[1]) * float(a[0]) for a in asks)
    denom = (bid_vol + ask_vol)
    if denom <= 0:
        return 50.0
    imb = (bid_vol - ask_vol) / denom  # -1..1
    return _clamp((imb + 1) / 2 * 100.0, 0.0, 100.0)

# ---- Gelişmiş kısa vade metrikleri ----
async def get_altcoin_short_metrics_enhanced(sample_top_n: int = 120) -> Dict[str, float]:
    """
    Genişletilmiş altcoin metrikleri:
      - hacim ağırlıklı fiyat değişimi
      - net io (io_utils.market_inout)
      - ortalama orderbook imbalance (top semboller için)
      - whale counts ve global taker ratio (ortalama)
    """
    tickers = await binance_api.get_all_24h_tickers()
    # USDT pariteleri ve filtreleme
    alts = []
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
    symbols = [s for s, _ in alts[:sample_top_n]]

    market_io = await io_utils.market_inout()
    # Whale ve taker ratio paralel hesapla
    whale_map_task = asyncio.create_task(io_utils.compute_whale_counts(symbols))
    taker_map_task = asyncio.create_task(io_utils.compute_taker_ratio(symbols))

    # Hacim ağırlıklı değişim
    sum_vol = 0.0
    sum_wchg = 0.0
    for sym in symbols:
        # tickers dict lookup cheaper than calling API again; find ticker
        t = next((x for x in tickers if x.get("symbol") == sym), None)
        if not t:
            continue
        qvol = float(t.get("quoteVolume", 0.0))
        chg = float(t.get("priceChangePercent", 0.0))
        sum_vol += qvol
        sum_wchg += chg * qvol

    wchg = (sum_wchg / sum_vol) if sum_vol > 0 else 0.0

    whale_map = await whale_map_task
    taker_map = await taker_map_task

    # Aggregate whale counts and taker ratios
    total_whale_buy = sum(v.get("whale_buy_count", 0) for v in whale_map.values())
    total_whale_sell = sum(v.get("whale_sell_count", 0) for v in whale_map.values())
    # Weighted average taker buy ratio across symbols:
    avg_taker_ratio = 0.0
    count_tr = 0
    for sym in symbols:
        tr = taker_map.get(sym)
        if tr is None:
            continue
        avg_taker_ratio += tr
        count_tr += 1
    avg_taker_ratio = (avg_taker_ratio / count_tr) if count_tr > 0 else 0.5

    # Compute average order book imbalance for top subset (limit concurrency)
    imb_tasks = [compute_order_book_imbalance(sym, top_n=8) for sym in symbols[:40]]  # sadece top40 için
    imbs = await asyncio.gather(*imb_tasks, return_exceptions=True)
    imbs_clean = [v for v in imbs if isinstance(v, (int, float))]
    avg_imb = (sum(imbs_clean) / len(imbs_clean)) if imbs_clean else 50.0

    # net_io: aggregate from market_io where available
    net_io = 0.0
    for sym in symbols:
        if sym in market_io:
            net_io += (market_io[sym].get("buy", 0.0) - market_io[sym].get("sell", 0.0))

    return {
        "price_change": wchg,
        "net_io": net_io,
        "volume": sum_vol,
        "avg_orderbook_imbalance": avg_imb,  # 0..100 (50 neutral)
        "whale_buy_total": total_whale_buy,
        "whale_sell_total": total_whale_sell,
        "avg_taker_buy_ratio": avg_taker_ratio
    }

# ---- BTC kısa vade (aynı mantık) ----
async def get_btc_short_metrics_enhanced() -> Dict[str, float]:
    t = await binance_api.get_24h_ticker("BTCUSDT")
    market_io = await io_utils.market_inout()
    chg = float(t.get("priceChangePercent", 0.0)) if t else 0.0
    qvol = float(t.get("quoteVolume", 0.0)) if t else 0.0
    net_io = 0.0
    if "BTCUSDT" in market_io:
        net_io = market_io["BTCUSDT"].get("buy", 0.0) - market_io["BTCUSDT"].get("sell", 0.0)

    # BTC orderbook imbalance
    imb = await compute_order_book_imbalance("BTCUSDT", top_n=20)

    # BTC whale/taker (küçük set)
    whale_map = await io_utils.compute_whale_counts(["BTCUSDT"], limit_per_symbol=500)
    taker_map = await io_utils.compute_taker_ratio(["BTCUSDT"], limit_per_symbol=500)
    wb = whale_map.get("BTCUSDT", {}).get("whale_buy_count", 0)
    ws = whale_map.get("BTCUSDT", {}).get("whale_sell_count", 0)
    tr = taker_map.get("BTCUSDT", 0.5)

    return {
        "price_change": chg,
        "net_io": net_io,
        "volume": qvol,
        "orderbook_imbalance": imb,
        "whale_buy": wb,
        "whale_sell": ws,
        "taker_buy_ratio": tr
    }

# ---- Skorlama: yeni metrikleri de hesaba katan 0..100 dönüşümleri ----
def score_orderbook_imbalance(imb_0_100: float) -> float:
    # 50 neutral, >50 buyer bias -> pozitif
    return imb_0_100  # direkt 0..100

def score_whale_signals(whale_buy: int, whale_sell: int) -> float:
    # Basit: (buy - sell) / (buy+sell) -> normalize
    total = whale_buy + whale_sell
    if total == 0:
        return 50.0
    diff = (whale_buy - whale_sell) / total  # -1..1
    return _clamp((diff + 1) / 2 * 100.0, 0.0, 100.0)

def score_taker_ratio(ratio: float) -> float:
    # ratio 0..1 (1 => taker-buy baskın), 0.5 neutral
    return _clamp((ratio) * 100.0, 0.0, 100.0)

# ---- Ana toplayıcı ---------------------------------------------------------
async def collect_ap_scores_enhanced() -> Dict[str, float]:
    btc_dom, alt_short_e, btc_short_e = await asyncio.gather(
        get_btc_dominance(),
        get_altcoin_short_metrics_enhanced(),
        get_btc_short_metrics_enhanced()
    )
    breadth = await get_long_term_breadth(top_n=30)

    # S1: alt vs btc short (fark + dom bonus)
    s1 = score_alt_vs_btc_short(alt_short_e["price_change"], btc_short_e["price_change"], btc_dom)

    # S2: alt short (fiyat + net_io + whale signals + taker ratio + OB imbalance)
    s_price = _normalize_0_100(alt_short_e["price_change"], -6.0, 6.0)
    s_io = _normalize_0_100(alt_short_e["net_io"], -500_000_000.0, 500_000_000.0)
    s_whale = score_whale_signals(alt_short_e["whale_buy_total"], alt_short_e["whale_sell_total"])
    s_taker = score_taker_ratio(alt_short_e["avg_taker_buy_ratio"])
    s_imb = score_orderbook_imbalance(alt_short_e["avg_orderbook_imbalance"])

    # ağırlıklar (özelleştirilebilir)
    s2 = _clamp(0.35*s_price + 0.25*s_io + 0.15*s_whale + 0.15*s_taker + 0.10*s_imb, 0, 100)

    # S3: long term breadth
    s3 = score_long_term(breadth)

    return {
        "alt_vs_btc_short": s1,
        "alt_short": s2,
        "coins_long": s3,
        # yardımcı metrikler (rapor veya debug için)
        "meta": {
            "btc_dominance": btc_dom,
            "alt_price_change": alt_short_e["price_change"],
            "alt_net_io": alt_short_e["net_io"],
            "alt_whale_buy": alt_short_e["whale_buy_total"],
            "alt_whale_sell": alt_short_e["whale_sell_total"],
            "alt_taker_ratio": alt_short_e["avg_taker_buy_ratio"],
            "alt_avg_imbalance": alt_short_e["avg_orderbook_imbalance"],
            "btc_orderbook_imbalance": btc_short_e.get("orderbook_imbalance", 50.0),
            "btc_whale_buy": btc_short_e.get("whale_buy", 0),
            "btc_whale_sell": btc_short_e.get("whale_sell", 0),
            "btc_taker_ratio": btc_short_e.get("taker_buy_ratio", 0.5)
        }
    }

# Dışa yardımcı: rapor satırları (güncellenmiş)
async def build_ap_report_lines_enhanced() -> List[str]:
    scores = await collect_ap_scores_enhanced()
    meta = scores.get("meta", {})
    return [
        f"Altların Kısa Vadede Btc'ye Karşı Gücü(0-100): {_decimal_tr(scores['alt_vs_btc_short'])}",
        f"Altların Kısa Vadede Gücü(0-100): {_decimal_tr(scores['alt_short'])}  (Whales: {meta.get('alt_whale_buy')}/{meta.get('alt_whale_sell')}, TakerBuyRatio: {_decimal_tr(meta.get('alt_taker_ratio',0.5)*100) }%)",
        f"Coinlerin Uzun Vadede Gücü(0-100): {_decimal_tr(scores['coins_long'])}"
    ]
