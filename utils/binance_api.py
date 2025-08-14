# utils/binance_api.py
import os
import asyncio
import httpx
import logging
import time
import hmac
import hashlib
import json
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import urlencode

try:
    import websockets
except Exception:
    websockets = None

LOG = logging.getLogger("binance_api")
LOG.addHandler(logging.NullHandler())

BASE = "https://api.binance.com/api/v3"
FAPI_BASE = "https://fapi.binance.com"
WS_BASE = "wss://stream.binance.com:9443"

CONCURRENCY = int(os.getenv("BINANCE_CONCURRENCY", "10"))
_semaphore = asyncio.Semaphore(CONCURRENCY)
_client: Optional[httpx.AsyncClient] = None

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
FAPI_KEY = os.getenv("BINANCE_FAPI_KEY") or API_KEY
FAPI_SECRET = os.getenv("BINANCE_FAPI_SECRET") or API_SECRET

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20.0)
    return _client

async def _get(path: str, params: dict = None, base: str = "") -> Any:
    if base:
        full = f"{base}{path}"
    else:
        full = path if path.startswith("http") else f"{BASE}{path}"
    client = get_client()
    async with _semaphore:
        for attempt in range(3):
            try:
                r = await client.get(full, params=params)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                LOG.warning("GET %s failed (attempt %s): %s", full, attempt+1, e)
                if attempt == 2:
                    raise
                await asyncio.sleep(0.25)

async def _post(path: str, data: dict = None, base: str = "") -> Any:
    if base:
        full = f"{base}{path}"
    else:
        full = path if path.startswith("http") else f"{BASE}{path}"
    client = get_client()
    async with _semaphore:
        for attempt in range(3):
            try:
                r = await client.post(full, data=data)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                LOG.warning("POST %s failed (attempt %s): %s", full, attempt+1, e)
                if attempt == 2:
                    raise
                await asyncio.sleep(0.25)

def _sign(params: dict, secret: str) -> str:
    q = urlencode(params, doseq=True)
    return hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()

async def _signed_request(method: str, path: str, params: dict = None, base: str = BASE, key: Optional[str] = None, secret: Optional[str] = None) -> Any:
    params = params.copy() if params else {}
    params["timestamp"] = int(time.time() * 1000)
    s = _sign(params, secret or API_SECRET or "")
    params["signature"] = s
    headers = {}
    used_key = key or API_KEY
    if used_key:
        headers["X-MBX-APIKEY"] = used_key

    client = get_client()
    url = f"{base}{path}" if not path.startswith("http") else path
    async with _semaphore:
        method = method.upper()
        if method == "GET":
            r = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            r = await client.post(url, data=params, headers=headers)
        elif method == "DELETE":
            r = await client.delete(url, params=params, headers=headers)
        else:
            raise ValueError("Unsupported HTTP method for signed request")
        r.raise_for_status()
        return r.json()

# Market REST
async def get_price(symbol: str) -> Optional[float]:
    try:
        data = await _get("/ticker/price", params={"symbol": symbol})
        return float(data.get("price"))
    except Exception as e:
        LOG.warning("get_price %s failed: %s", symbol, e)
        return None

async def get_24h_ticker(symbol: Optional[str] = None) -> Optional[dict]:
    try:
        params = {"symbol": symbol} if symbol else None
        return await _get("/ticker/24hr", params=params)
    except Exception as e:
        LOG.warning("get_24h_ticker %s failed: %s", symbol, e)
        return None



# /ap icin
async def get_all_24h_tickers() -> list:
    """Tüm 24h ticker bilgilerini döndürür"""
    # ... EKLENDİ: AP hesaplamalarında kullanılacak tüm ticker verilerini çekmek için
    return await _get("/ticker/24hr")





async def get_order_book(symbol: str, limit: int = 100) -> Optional[dict]:
    try:
        return await _get("/depth", params={"symbol": symbol, "limit": limit})
    except Exception as e:
        LOG.warning("get_order_book %s failed: %s", symbol, e)
        return None

async def get_klines(symbol: str, interval: str = "1h", limit: int = 500) -> Optional[List[List]]:
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return await _get("/klines", params=params)
    except Exception as e:
        LOG.warning("get_klines %s failed: %s", symbol, e)
        return None

async def get_multiple_klines(symbols: List[str], interval: str = "1h", limit: int = 100) -> Dict[str, Optional[List[List]]]:
    tasks = [get_klines(s, interval=interval, limit=limit) for s in symbols]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    out: Dict[str, Optional[List[List]]] = {}
    for s, r in zip(symbols, res):
        out[s] = None if isinstance(r, Exception) else r
    return out

async def get_all_symbols() -> List[str]:
    try:
        data = await _get("/exchangeInfo")
        syms = []
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING":
                syms.append(s.get("symbol"))
        return sorted(list(set(syms)))
    except Exception as e:
        LOG.warning("get_all_symbols failed: %s", e)
        return []

async def exchange_info_details() -> Dict[str, Any]:
    try:
        data = await _get("/exchangeInfo")
        out = {}
        for s in data.get("symbols", []):
            out[s.get("symbol")] = s
        return out
    except Exception as e:
        LOG.warning("exchange_info_details failed: %s", e)
        return {}

# Futures
async def get_funding_rate(symbol: Optional[str] = None, limit: int = 100) -> Optional[Any]:
    try:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        return await _get("/fapi/v1/fundingRate", params=params, base=FAPI_BASE)
    except Exception as e:
        LOG.warning("get_funding_rate %s failed: %s", symbol, e)
        return None

async def get_open_interest(symbol: str) -> Optional[dict]:
    try:
        return await _get("/fapi/v1/openInterest", params={"symbol": symbol}, base=FAPI_BASE)
    except Exception as e:
        LOG.warning("get_open_interest %s failed: %s", symbol, e)
        return None

# Signed trading helpers
async def create_spot_order(symbol: str, side: str, type_: str, quantity: Optional[float] = None, price: Optional[float] = None, extra: dict = None) -> Any:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("Spot API key/secret not set in BINANCE_API_KEY/BINANCE_API_SECRET")
    params = {"symbol": symbol, "side": side, "type": type_}
    if quantity is not None:
        params["quantity"] = str(quantity)
    if price is not None:
        params["price"] = str(price)
    if extra:
        params.update(extra)
    return await _signed_request("POST", "/api/v3/order", params=params, base=BASE, key=API_KEY, secret=API_SECRET)

async def cancel_spot_order(symbol: str, orderId: int = None, origClientOrderId: str = None) -> Any:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("Spot API key/secret not set")
    params = {"symbol": symbol}
    if orderId:
        params["orderId"] = int(orderId)
    if origClientOrderId:
        params["origClientOrderId"] = origClientOrderId
    return await _signed_request("DELETE", "/api/v3/order", params=params, base=BASE, key=API_KEY, secret=API_SECRET)

async def get_account_info_spot() -> Any:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("Spot API key/secret not set")
    return await _signed_request("GET", "/api/v3/account", params={}, base=BASE, key=API_KEY, secret=API_SECRET)

async def create_futures_order(symbol: str, side: str, type_: str, quantity: Optional[float] = None, price: Optional[float] = None, extra: dict = None) -> Any:
    if not FAPI_KEY or not FAPI_SECRET:
        raise RuntimeError("Futures API key/secret not set in BINANCE_FAPI_KEY/BINANCE_FAPI_SECRET")
    params = {"symbol": symbol, "side": side, "type": type_}
    if quantity is not None:
        params["quantity"] = str(quantity)
    if price is not None:
        params["price"] = str(price)
    if extra:
        params.update(extra)
    return await _signed_request("POST", "/fapi/v1/order", params=params, base=FAPI_BASE, key=FAPI_KEY, secret=FAPI_SECRET)

async def cancel_futures_order(symbol: str, orderId: int = None, origClientOrderId: str = None) -> Any:
    if not FAPI_KEY or not FAPI_SECRET:
        raise RuntimeError("Futures API key/secret not set")
    params = {"symbol": symbol}
    if orderId:
        params["orderId"] = int(orderId)
    if origClientOrderId:
        params["origClientOrderId"] = origClientOrderId
    return await _signed_request("DELETE", "/fapi/v1/order", params=params, base=FAPI_BASE, key=FAPI_KEY, secret=FAPI_SECRET)

async def get_futures_account() -> Any:
    if not FAPI_KEY or not FAPI_SECRET:
        raise RuntimeError("Futures API key/secret not set")
    return await _signed_request("GET", "/fapi/v2/account", params={}, base=FAPI_BASE, key=FAPI_KEY, secret=FAPI_SECRET)

# WebSocket combined stream
async def _ws_listen(uri: str, message_handler: Callable[[dict], None], reconnect_delay: float = 1.0):
    if websockets is None:
        raise RuntimeError("websockets package required. pip install websockets")
    while True:
        try:
            LOG.info("Connecting WS %s", uri)
            async with websockets.connect(uri, max_size=2**25) as ws:
                LOG.info("WS connected: %s", uri)
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        res = message_handler(msg)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        LOG.exception("Error in ws message handler: %s", e)
        except asyncio.CancelledError:
            LOG.info("WS listener cancelled for %s", uri)
            raise
        except Exception as e:
            LOG.warning("Websocket error (%s), reconnecting in %.1fs: %s", uri, reconnect_delay, e)
            await asyncio.sleep(reconnect_delay)

def _stream_name(symbol: str, stream: str) -> str:
    return f"{symbol.lower()}@{stream}"

async def start_combined_stream(streams: List[str], message_handler: Callable[[dict], None]):
    if not streams:
        raise ValueError("streams list empty")
    joined = "/".join([s.lower() for s in streams])
    uri = f"{WS_BASE}/stream?streams={joined}"
    return await _ws_listen(uri, message_handler)

class BinanceClient:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.tasks: List[asyncio.Task] = []

    def run_task(self, coro):
        t = self.loop.create_task(coro)
        self.tasks.append(t)
        return t

    def cancel_all(self):
        for t in self.tasks:
            t.cancel()
        self.tasks = []

    async def price(self, symbol: str) -> Optional[float]:
        return await get_price(symbol)

    async def kline(self, symbol: str, interval: str, limit: int = 500):
        return await get_klines(symbol, interval=interval, limit=limit)

    async def funding(self, symbol: Optional[str] = None, limit: int = 100):
        return await get_funding_rate(symbol=symbol, limit=limit)

    async def exchange_info(self):
        return await exchange_info_details()

    def start_combined(self, streams: List[str], handler: Callable[[dict], None]):
        return self.run_task(start_combined_stream(streams, handler))
