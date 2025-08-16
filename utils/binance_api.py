import os
import time
import hmac
import hashlib
import json
import asyncio
import logging
import httpx
import websockets
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from utils.config import CONFIG

# -------------------------------------------------------------
# Logger
# -------------------------------------------------------------
LOG = logging.getLogger(__name__)

# -------------------------------------------------------------
# HTTP Katmanı: Retry + Exponential Backoff + TTL Cache
# -------------------------------------------------------------
class BinanceHTTPClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=CONFIG.BINANCE.BASE_URL, timeout=15)
        self.sem = asyncio.Semaphore(CONFIG.BINANCE.CONCURRENCY)
        self._cache: Dict[str, Tuple[float, Any]] = {}

    async def _request(self, method: str, path: str, params: Optional[dict] = None, signed: bool = False, futures: bool = False) -> Any:
        base_url = CONFIG.BINANCE.FAPI_URL if futures else CONFIG.BINANCE.BASE_URL
        headers = {}
        params = params or {}

        if signed:
            ts = int(time.time() * 1000)
            params["timestamp"] = ts
            query = urlencode(params)
            signature = hmac.new(CONFIG.BINANCE.SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
            params["signature"] = signature
            headers["X-MBX-APIKEY"] = CONFIG.BINANCE.API_KEY

        # TTL Cache key
        cache_key = f"{method}:{base_url}{path}:{json.dumps(params, sort_keys=True) if params else ''}"
        ttl = CONFIG.BINANCE.BINANCE_TICKER_TTL
        if ttl > 0 and cache_key in self._cache:
            ts_cache, data = self._cache[cache_key]
            if time.time() - ts_cache < ttl:
                return data

        attempt = 0
        while True:
            attempt += 1
            try:
                async with self.sem:
                    r = await self.client.request(method, base_url + path, params=params, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if ttl > 0:
                        self._cache[cache_key] = (time.time(), data)
                    return data

                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 1))
                    delay = min(2 ** attempt, 60) + retry_after
                    LOG.warning("Rate limited. Sleeping %ss", delay)
                    await asyncio.sleep(delay)
                    continue

                r.raise_for_status()
            except Exception as e:
                delay = min(2 ** attempt, 60)
                LOG.error("Request error %s, retrying in %s", e, delay)
                await asyncio.sleep(delay)

http = BinanceHTTPClient()

# -------------------------------------------------------------
# BinanceClient Wrapper
# -------------------------------------------------------------
class BinanceClient:
    """
    REST + WS wrapper. main.py tarafında kullanılacak.
    """
    def __init__(self):
        self.http = http
        self.loop = asyncio.get_running_loop()
        self.ws_tasks: List[asyncio.Task] = []

    # --- REST fonksiyonlar ---
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        return await self.http._request("GET", "/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        return await self.http._request("GET", "/api/v3/trades", {"symbol": symbol.upper(), "limit": limit})

    async def get_agg_trades(self, symbol: str, limit: int = 500) -> List[Dict[str, Any]]:
        return await self.http._request("GET", "/api/v3/aggTrades", {"symbol": symbol.upper(), "limit": limit})

    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 500) -> List[List[Any]]:
        return await self.http._request("GET", "/api/v3/klines", {"symbol": symbol.upper(), "interval": interval, "limit": limit})

    async def get_24h_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.http._request("GET", "/api/v3/ticker/24hr", {"symbol": symbol.upper()})

    async def get_all_24h_tickers(self) -> List[Dict[str, Any]]:
        return await self.http._request("GET", "/api/v3/ticker/24hr")

    async def get_all_symbols(self) -> List[str]:
        data = await self.http._request("GET", "/api/v3/exchangeInfo")
        return [s["symbol"] for s in data["symbols"]]

    async def exchange_info_details(self) -> Dict[str, Any]:
        return await self.http._request("GET", "/api/v3/exchangeInfo")

    async def get_account_info(self) -> Dict[str, Any]:
        return await self.http._request("GET", "/api/v3/account", signed=True)

    async def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: Optional[float] = None) -> Dict[str, Any]:
        params = {"symbol": symbol.upper(), "side": side, "type": type_, "quantity": quantity}
        if price:
            params["price"] = price
        return await self.http._request("POST", "/api/v3/order", params=params, signed=True)

    async def futures_position_info(self) -> List[Dict[str, Any]]:
        return await self.http._request("GET", "/fapi/v2/positionRisk", signed=True, futures=True)

    # --- WS fonksiyonları ---
    async def ws_subscribe(self, url: str, callback):
        while True:
            try:
                async with websockets.connect(url) as ws:
                    async for msg in ws:
                        data = json.loads(msg)
                        await callback(data)
            except Exception as e:
                LOG.error("WS error: %s", e)
                await asyncio.sleep(5)
                continue

    async def ws_ticker(self, symbol: str, callback):
        url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@ticker"
        await self.ws_subscribe(url, callback)

    async def ws_trades(self, symbol: str, callback):
        url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
        await self.ws_subscribe(url, callback)

    async def ws_order_book(self, symbol: str, depth: int, callback):
        url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@depth{depth}@100ms"
        await self.ws_subscribe(url, callback)

# -------------------------------------------------------------
# Mevcut tüm metrik ve util fonksiyonlar bozulmadan kalıyor
# (order_book_imbalance, whale_trades, taker_buy_sell_ratio, volume_delta,
# spread, vwap_depth_impact, liquidity_score, trade_size_distribution,
# short_term_momentum, market_order_price_impact, fetch_many)
# Kodun tamamını yukarıdaki gibi bırakabilirsin; sadece BinanceClient eklendi
