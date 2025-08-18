##coingecko_utils.py
#79
import requests
import logging

LOG = logging.getLogger("coingecko_utils")
LOG.addHandler(logging.NullHandler())

class CoinGeckoAPI:
    BASE_URL = "https://api.coingecko.com/api/v3"
    # API anahtarı doğrudan eklenmiş
    API_KEY = "CG-eiMds8XoZG8SPWRR7ia7fzKv"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "CG-API-KEY": self.API_KEY
        })

    def get_price(self, ids, vs_currencies, include_market_data=False):
        url = f"{self.BASE_URL}/simple/price"
        params = {
            "ids": ids,
            "vs_currencies": vs_currencies,
            "include_market_data": str(include_market_data).lower()
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            LOG.error(f"get_price error: {e}")
            return {}

    def get_market_data(self, ids, vs_currency, order="market_cap_desc", per_page=100, page=1):
        url = f"{self.BASE_URL}/coins/markets"
        params = {
            "ids": ids,
            "vs_currency": vs_currency,
            "order": order,
            "per_page": per_page,
            "page": page
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            LOG.error(f"get_market_data error: {e}")
            return []

    def get_trending_coins(self):
        url = f"{self.BASE_URL}/search/trending"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get("coins", [])
        except Exception as e:
            LOG.error(f"get_trending_coins error: {e}")
            return []

    def get_coin_categories(self):
        url = f"{self.BASE_URL}/coins/categories/list"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            LOG.error(f"get_coin_categories error: {e}")
            return []

    def get_global_data(self):
        url = f"{self.BASE_URL}/global"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            LOG.error(f"get_global_data error: {e}")
            return {}
