# utils/coinglass_utils.py
import os
import logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

LOG = logging.getLogger("coinglass_utils")
LOG.addHandler(logging.NullHandler())

COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")
COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com/api"

# ETF sağlayıcıları ve sembolleri (CoinGlass API v4)
PROVIDER_MAP = {
    "BlackRock": ["IBIT", "ETHA"],
    "Fidelity": ["FBTC", "FETH"],
    "Grayscale": ["GBTC", "ETHE"]
}

# ------------------ ETF Fiyat ve Akış Verisi ------------------ #

def get_etf_flow(asset: str = "bitcoin") -> str:
    """
    Belirtilen varlık için ETF net akış raporu hazırlar.
    asset = 'bitcoin' veya 'ethereum'
    """
    if not COINGLASS_API_KEY:
        LOG.warning("Coinglass API key bulunamadı.")
        return "ETF verileri alınamadı: API key eksik."

    url = f"{COINGLASS_BASE_URL}/{asset}/etf/flow-history"
    headers = {"CG-API-KEY": COINGLASS_API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        if str(data.get("code")) != "0" or not data.get("data"):
            return f"{asset.upper()} için ETF verileri alınamadı."

        today_data = data["data"][0]
        yesterday_data = data["data"][1] if len(data["data"]) > 1 else None

        total_today = sum([etf.get("flow", 0) for etf in today_data.get("etfList", [])])
        total_yesterday = sum([etf.get("flow", 0) for etf in yesterday_data.get("etfList", [])]) if yesterday_data else 0
        change = total_today - total_yesterday
        trend_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

        # Sağlayıcı bazlı toplamlar
        provider_lines = []
        for provider, tickers in PROVIDER_MAP.items():
            prov_total = sum(
                etf.get("flow", 0) for etf in today_data.get("etfList", []) if etf.get("symbol") in tickers
            )
            provider_lines.append(f"{provider}: {prov_total:,.0f} $")

        report = (
            f"📊 {asset.upper()} ETF Net Akış\n"
            f"Toplam: {total_today:,.0f} $ ({'+' if change>0 else ''}{change:,.0f} $) {trend_emoji}\n"
            + "\n".join(provider_lines)
        )
        return report

    except Exception as e:
        LOG.warning("[Coinglass] %s ETF verisi alınamadı: %s", asset, e)
        return f"{asset.upper()} için ETF verileri alınamadı."

def get_etf_price_history(asset: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Belirtilen varlık için ETF fiyat geçmişi verisini getirir.
    asset = 'bitcoin' veya 'ethereum'
    """
    if not COINGLASS_API_KEY:
        LOG.warning("Coinglass API key bulunamadı.")
        return {}

    url = f"{COINGLASS_BASE_URL}/{asset}/etf/price/history"
    headers = {"CG-API-KEY": COINGLASS_API_KEY}
    params = {"start": start_date, "end": end_date}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if str(data.get("code")) != "0" or not data.get("data"):
            LOG.warning("%s ETF fiyat verisi boş döndü", asset)
            return {}
        return data["data"]
    except Exception as e:
        LOG.warning("[Coinglass] %s ETF fiyat verisi alınamadı: %s", asset, e)
        return {}
