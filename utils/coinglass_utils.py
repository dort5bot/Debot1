# utils/coinglass_utils.py

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

LOG = logging.getLogger("coinglass_utils")
LOG.addHandler(logging.NullHandler())

COINGLASS_BASE = os.getenv("COINGLASS_BASE", "https://open-api.coinglass.com/api/pro/v1")
COINGLASS_KEY = os.getenv("COINGLASS_API_KEY", "")

HEADERS = {"coinglassSecret": COINGLASS_KEY} if COINGLASS_KEY else {}

# ------------------ Genel Futures Verileri ------------------ #

async def get_funding_rate(symbol: str) -> Optional[Dict[str, Any]]:
    """Tüm borsalardaki funding rate verilerini getirir."""
    if not COINGLASS_KEY:
        return None
    try:
        url = f"{COINGLASS_BASE}/futures/funding_rate"
        params = {"symbol": symbol}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        LOG.warning("[Coinglass] Funding rate alınamadı: %s", e)
        return None


async def get_open_interest(symbol: str) -> Optional[Dict[str, Any]]:
    """Toplam açık pozisyon (Open Interest) verisini getirir."""
    if not COINGLASS_KEY:
        return None
    try:
        url = f"{COINGLASS_BASE}/futures/openInterest"
        params = {"symbol": symbol}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        LOG.warning("[Coinglass] Open Interest alınamadı: %s", e)
        return None


async def get_long_short_ratio(symbol: str) -> Optional[Dict[str, Any]]:
    """Long/Short oranı (pozisyon yüzdesi) verisini getirir."""
    if not COINGLASS_KEY:
        return None
    try:
        url = f"{COINGLASS_BASE}/futures/longShortRate"
        params = {"symbol": symbol}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        LOG.warning("[Coinglass] Long/Short oranı alınamadı: %s", e)
        return None


async def get_taker_volume(symbol: str, interval: str = "15m") -> Optional[Dict[str, float]]:
    """
    Taker Buy/Sell hacimlerini getirir.
    Beklenen dönüş: {'buy': float, 'sell': float}
    """
    if not COINGLASS_KEY:
        return None
    try:
        url = f"{COINGLASS_BASE}/futures/taker_volume"
        params = {"symbol": symbol, "interval": interval}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=HEADERS, params=params)
            r.raise_for_status()
            data = r.json()
            last = (data.get("data") or [])[-1] if isinstance(data.get("data"), list) else None
            if not last:
                return None
            buy = float(last.get("buyVol", 0.0))
            sell = float(last.get("sellVol", 0.0))
            return {"buy": buy, "sell": sell}
    except Exception as e:
        LOG.warning("[Coinglass] Taker volume alınamadı (%s %s): %s", symbol, interval, e)
        return None

# ------------------ ETF Verileri ------------------ #

PROVIDER_MAP = {
    "BlackRock": ["IBIT", "ETHA"],  # BTC ve ETH ETF sembolleri
    "Fidelity": ["FBTC", "FETH"],
    "Grayscale": ["GBTC", "ETHE"]
}

async def get_etf_flow_history(asset: str) -> List[Dict[str, Any]]:
    """Belirtilen varlık için ETF Net Akış geçmişini getirir."""
    if not COINGLASS_KEY:
        return []
    try:
        url = f"{COINGLASS_BASE}/etf/{asset}/flow-history"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            LOG.debug("[ETF] API Response for %s: %s", asset, data)
            return data.get("data", [])
    except Exception as e:
        LOG.warning("[Coinglass] %s ETF verisi alınamadı: %s", asset, e)
        return []


async def parse_etf_report(asset: str) -> str:
    """Verilen varlık için ETF raporu hazırlar."""
    raw_data = await get_etf_flow_history(asset)
    if not raw_data:
        return f"{asset.upper()} için veri alınamadı."

    today_data = raw_data[0]
    yesterday_data = raw_data[1] if len(raw_data) > 1 else None

    total_today = sum([etf["flow"] for etf in today_data["etfList"]])
    total_yesterday = sum([etf["flow"] for etf in yesterday_data["etfList"]]) if yesterday_data else 0
    change = total_today - total_yesterday

    trend_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

    provider_lines = []
    for provider, tickers in PROVIDER_MAP.items():
        prov_total = sum(
            etf["flow"] for etf in today_data["etfList"] if etf["symbol"] in tickers
        )
        provider_lines.append(f"{provider}: {prov_total:,.0f} $")

    report = (
        f"📊 {asset.upper()} ETF Net Akış\n"
        f"Total: {total_today:,.0f} $ ({'+' if change>0 else ''}{change:,.0f} $) {trend_emoji}\n"
        + "\n".join(provider_lines)
    )
    return report
