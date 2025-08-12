##coingecko_utils.py
##
import os
import requests
from dotenv import load_dotenv

load_dotenv()

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
BASE_URL = "https://pro-api.coingecko.com/api/v3"

headers = {
    "x-cg-pro-api-key": COINGECKO_API_KEY
}

def get_price(symbol: str, currency: str = "usd"):
    """
    Coingecko üzerinden coin fiyatını getirir.
    symbol: 'bitcoin', 'ethereum' vb.
    """
    try:
        url = f"{BASE_URL}/simple/price"
        params = {"ids": symbol, "vs_currencies": currency}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get(symbol, {}).get(currency)
    except Exception as e:
        print(f"[Coingecko] Fiyat verisi alınamadı: {e}")
        return None

def get_market_data(symbol: str):
    """
    Piyasa değeri, hacim, fiyat değişimleri gibi verileri döndürür.
    """
    try:
        url = f"{BASE_URL}/coins/{symbol}"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return {
            "symbol": symbol,
            "price_usd": data["market_data"]["current_price"]["usd"],
            "market_cap": data["market_data"]["market_cap"]["usd"],
            "volume_24h": data["market_data"]["total_volume"]["usd"],
            "price_change_24h": data["market_data"]["price_change_percentage_24h"]
        }
    except Exception as e:
        print(f"[Coingecko] Market verisi alınamadı: {e}")
        return None

def get_historical_data(symbol: str, days: int = 30):
    """
    Günlük geçmiş fiyat verilerini döndürür.
    """
    try:
        url = f"{BASE_URL}/coins/{symbol}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Coingecko] Geçmiş veri alınamadı: {e}")
        return None
