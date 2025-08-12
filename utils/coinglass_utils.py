##coinglass_utils.py
##

import os
import requests
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

def get_etf_flow():
    """
    BTC ve ETH spot ETF net akış verilerini getirir.
    """
    try:
        url = f"{BASE_URL}/etf/fundflow"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Coinglass] ETF verisi alınamadı: {e}")
        return None
