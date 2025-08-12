##coinglass_utils.py
##

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY")
BASE_URL = "https://open-api.coinglass.com/api/pro/v1"

headers = {
    "coinglassSecret": COINGLASS_API_KEY
}

def get_funding_rate(symbol: str):
    """
    Tüm borsalardaki funding rate verilerini getirir.
    """
    try:
        url = f"{BASE_URL}/futures/funding_rate"
        params = {"symbol": symbol}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Coinglass] Funding rate verisi alınamadı: {e}")
        return None

def get_open_interest(symbol: str):
    """
    Toplam açık pozisyon (Open Interest) verisini getirir.
    """
    try:
        url = f"{BASE_URL}/futures/openInterest"
        params = {"symbol": symbol}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Coinglass] Open Interest verisi alınamadı: {e}")
        return None

def get_long_short_ratio(symbol: str):
    """
    Long/Short oranı (pozisyon yüzdesi) verisini getirir.
    """
    try:
        url = f"{BASE_URL}/futures/longShortRate"
        params = {"symbol": symbol}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Coinglass] Long/Short verisi alınamadı: {e}")
        return None

###♦️
# ETF sağlayıcı isimleri - ID eşleştirmesi (Coinglass API'ye göre)
PROVIDER_MAP = {
    "BlackRock": ["IBIT", "ETHA"],  # BTC ve ETH ETF sembolleri
    "Fidelity": ["FBTC", "FETH"],
    "Grayscale": ["GBTC", "ETHE"]
}

def get_etf_flow_history(asset: str):
    """
    BTC veya ETH ETF günlük akış verilerini getirir.
    asset: 'bitcoin' veya 'ethereum'
    """
    try:
        url = f"{BASE_URL}/etf/{asset}/flow-history"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"[Coinglass] {asset} ETF verisi alınamadı: {e}")
        return []

def parse_etf_report(asset: str):
    """
    Verilen varlık için ETF raporu hazırlar.
    """
    raw_data = get_etf_flow_history(asset)
    if not raw_data:
        return f"{asset.upper()} için veri alınamadı."

    # Son 2 gün verisi (bugün ve dün)
    today_data = raw_data[0]
    yesterday_data = raw_data[1] if len(raw_data) > 1 else None

    total_today = sum([etf["flow"] for etf in today_data["etfList"]])
    total_yesterday = sum([etf["flow"] for etf in yesterday_data["etfList"]]) if yesterday_data else 0
    change = total_today - total_yesterday

    trend_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

    # Sağlayıcı bazlı veriler
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


###♦️




