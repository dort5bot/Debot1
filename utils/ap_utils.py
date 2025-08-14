# utils/ap_utils.py
import asyncio
from utils import binance_api, io_utils

STABLE_QUOTES = ["USDT", "USDC", "BUSD", "FDUSD"]

async def get_btc_dominance():
    """BTC Dominance = BTC hacmi / toplam piyasa hacmi"""
    tickers = await binance_api.get_all_24h_tickers()
    total_vol = 0
    btc_vol = 0
    for t in tickers:
        symbol = t["symbol"]
        vol = float(t["quoteVolume"])
        total_vol += vol
        if symbol == "BTCUSDT":
            btc_vol += vol
    dominance = (btc_vol / total_vol) * 100 if total_vol > 0 else 0
    return dominance

async def get_altcoin_data():
    """Altcoin hacim, fiyat değişimi ve net in/out verilerini döndürür"""
    tickers = await binance_api.get_all_24h_tickers()
    market_io = await io_utils.market_inout()

    alt_vol = 0
    alt_change = 0
    alt_io = 0
    alt_usd_share = 0

    for t in tickers:
        symbol = t["symbol"]
        quote = None
        for q in STABLE_QUOTES:
            if symbol.endswith(q):
                quote = q
                break
        if not quote or symbol.startswith("BTC"):
            continue  # BTC ve stable'ları atla

        vol = float(t["quoteVolume"])
        price_change = float(t["priceChangePercent"])

        alt_vol += vol
        alt_change += price_change
        alt_usd_share += vol

        # market_io dict: {"BTCUSDT": {"buy": x, "sell": y}, ...}
        if symbol in market_io:
            buy = market_io[symbol]["buy"]
            sell = market_io[symbol]["sell"]
            alt_io += (buy - sell)

    return {
        "volume": alt_vol,
        "price_change": alt_change,
        "net_io": alt_io,
        "usd_share": alt_usd_share
    }

async def get_btc_data():
    """BTC hacim, net in/out verileri"""
    ticker = await binance_api.get_24h_ticker("BTCUSDT")
    market_io = await io_utils.market_inout()
    btc_vol = float(ticker["quoteVolume"])
    btc_change = float(ticker["priceChangePercent"])
    btc_io = 0
    if "BTCUSDT" in market_io:
        buy = market_io["BTCUSDT"]["buy"]
        sell = market_io["BTCUSDT"]["sell"]
        btc_io = buy - sell
    return {
        "volume": btc_vol,
        "price_change": btc_change,
        "net_io": btc_io
    }

async def collect_ap_metrics():
    """Tüm AP metriklerini tek seferde toplar"""
    dominance = await get_btc_dominance()
    alt_data, btc_data = await asyncio.gather(get_altcoin_data(), get_btc_data())
    return {
        "btc_dominance": dominance,
        "alt": alt_data,
        "btc": btc_data
    }





# utils/ap_utils.py  (devam) skorlama bölümü 

def score_btc_dominance(dominance: float) -> int:
    """
    BTC Dominance düşükse altcoin piyasası güçlü, yüksekse BTC baskın.
    0-40 -> +2 puan, 40-50 -> +1, 50-60 -> 0, 60-70 -> -1, 70+ -> -2
    """
    if dominance < 40:
        return 2
    elif dominance < 50:
        return 1
    elif dominance < 60:
        return 0
    elif dominance < 70:
        return -1
    else:
        return -2

def score_price_change(change: float) -> int:
    """
    Ortalama fiyat değişimi pozitifse +, negatifse - puan.
    >5% -> +2, 0-5% -> +1, 0 ila -5% -> -1, <-5% -> -2
    """
    if change > 5:
        return 2
    elif change > 0:
        return 1
    elif change > -5:
        return -1
    else:
        return -2

def score_net_io(io_value: float) -> int:
    """
    Net giriş (buy-sell) pozitifse piyasa talep görüyor.
    >500M -> +2, 0-500M -> +1, 0 ila -500M -> -1, <-500M -> -2
    """
    if io_value > 500_000_000:
        return 2
    elif io_value > 0:
        return 1
    elif io_value > -500_000_000:
        return -1
    else:
        return -2

def calculate_ap_score(metrics: dict) -> dict:
    """
    Tüm metriklerden toplam AP skoru üretir.
    Skor aralığı: -10 ile +10
    """
    btc_dom_score = score_btc_dominance(metrics["btc_dominance"])
    alt_price_score = score_price_change(metrics["alt"]["price_change"])
    alt_io_score = score_net_io(metrics["alt"]["net_io"])
    btc_price_score = score_price_change(metrics["btc"]["price_change"])
    btc_io_score = score_net_io(metrics["btc"]["net_io"])

    total_score = btc_dom_score + alt_price_score + alt_io_score + btc_price_score + btc_io_score

    return {
        "btc_dominance_score": btc_dom_score,
        "alt_price_score": alt_price_score,
        "alt_io_score": alt_io_score,
        "btc_price_score": btc_price_score,
        "btc_io_score": btc_io_score,
        "total_score": total_score
    }
    
