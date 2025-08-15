#binance_api.py
#
#
##
import os
import asyncio
import httpx
import logging
import time
import hmac
import hashlib
import json
from typing import List, Optional, Dict, Any, Callable, Tuple
from urllib.parse import urlencode

try:
    import websockets
except Exception:
    websockets = None

LOG = logging.getLogger("binance_api")
LOG.addHandler(logging.NullHandler())

BASE = "https://api.binance.com"
API_V3 = BASE + "/api/v3"
FAPI_BASE = "https://fapi.binance.com"
WS_BASE = "wss://stream.binance.com:9443"

CONCURRENCY = int(os.getenv("BINANCE_CONCURRENCY", "8"))
_semaphore = asyncio.Semaphore(CONCURRENCY)
_client: Optional[httpx.AsyncClient] = None

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
FAPI_KEY = os.getenv("BINANCE_FAPI_KEY") or API_KEY
FAPI_SECRET = os.getenv("BINANCE_FAPI_SECRET") or API_SECRET

# ---- Basit bellek içi cache (TTL) ----
_cache: Dict[str, Tuple[float, Any]] = {}  # key -> (expires_at, data)

def _now() -> float:
    return time.time()

def _cache_get(key: str):
    item = _cache.get(key)
    if not item:
        return None
    exp, data = item
    if _now() > exp:
        _cache.pop(key, None)
        return None
    return data

def _cache_set(key: str, data: Any, ttl: float):
    _cache[key] = (_now() + ttl, data)

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            headers={"User-Agent": "YsfBot/1.0 (+rate-limit-friendly)"},
        )
    return _client

async def _request(method: str, url: str, *, params=None, data=None, headers=None, max_tries: int = 4) -> Any:
    """
    Otomatik exponential backoff + 429 Retry-After desteği.
    """
    client = get_client()
    params = params or None
    data = data or None
    headers = headers or {}

    backoff = 0.4
    for attempt in range(1, max_tries + 1):
        try:
            async with _semaphore:
                r = await client.request(method, url, params=params, data=data, headers=headers)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after else backoff
                LOG.warning("429 Too Many Requests (%s). Sleeping %.2fs (attempt %s/%s)", url, sleep_s, attempt, max_tries)
                await asyncio.sleep(sleep_s)
                backoff = min(backoff * 2, 5.0)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            # 5xx -> backoff, diğerlerinde son denemede raise
            status = e.response.status_code
            if status >= 500 and attempt < max_tries:
                LOG.warning("HTTP %s %s failed %s, retrying in %.2fs", method, url, status, backoff)
                await asyncio.sleep(backoff); backoff = min(backoff * 2, 5.0)
                continue
            LOG.warning("HTTP error %s for %s %s: %s", status, method, url, e)
            raise
        except Exception as e:
            if attempt < max_tries:
                LOG.warning("Req error %s %s (attempt %s/%s): %s", method, url, attempt, max_tries, e)
                await asyncio.sleep(backoff); backoff = min(backoff * 2, 5.0)
                continue
            raise

async def _get(path: str, *, params: dict = None, base: str = API_V3, cache_ttl: float = 0.0, cache_key: Optional[str] = None) -> Any:
    url = path if path.startswith("http") else f"{base}{path}"
    if cache_ttl > 0:
        key = cache_key or f"GET:{url}:{json.dumps(params, sort_keys=True) if params else ''}"
        hit = _cache_get(key)
        if hit is not None:
            return hit
        data = await _request("GET", url, params=params)
        _cache_set(key, data, cache_ttl)
        return data
    return await _request("GET", url, params=params)

async def _post(path: str, *, data: dict = None, base: str = API_V3) -> Any:
    url = path if path.startswith("http") else f"{base}{path}"
    return await _request("POST", url, data=data)

def _sign(params: dict, secret: str) -> str:
    q = urlencode(params, doseq=True)
    return hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()

async def _signed_request(method: str, path: str, *, params: dict = None, base: str = API_V3, key: Optional[str] = None, secret: Optional[str] = None) -> Any:
    params = params.copy() if params else {}
    params["timestamp"] = int(time.time() * 1000)
    s = _sign(params, secret or API_SECRET or "")
    params["signature"] = s
    headers = {}
    used_key = key or API_KEY
    if used_key:
        headers["X-MBX-APIKEY"] = used_key
    url = path if path.startswith("http") else f"{base}{path}"
    return await _request(method.upper(), url, params=params if method.upper() != "POST" else None, data=params if method.upper() == "POST" else None, headers=headers)

# --------- Market REST ----------
async def get_price(symbol: str) -> Optional[float]:
    try:
        data = await _get("/ticker/price", params={"symbol": symbol}, base=API_V3, cache_ttl=5.0)
        return float(data.get("price"))
    except Exception as e:
        LOG.warning("get_price %s failed: %s", symbol, e)
        return None

async def get_24h_ticker(symbol: Optional[str] = None) -> Optional[dict]:
    try:
        params = {"symbol": symbol} if symbol else None
        return await _get("/ticker/24hr", params=params, base=API_V3, cache_ttl=5.0)
    except Exception as e:
        LOG.warning("get_24h_ticker %s failed: %s", symbol, e)
        return None

async def get_all_24h_tickers() -> list:
    """
    Tüm 24h ticker'lar (cache'li). 429'u azaltmak için 10–15 sn cache önerilir.
    """
    return await _get("/ticker/24hr", base=API_V3, cache_ttl=float(os.getenv("BINANCE_TICKER_TTL", "12")))

async def get_order_book(symbol: str, limit: int = 100) -> Optional[dict]:
    try:
        return await _get("/depth", params={"symbol": symbol, "limit": limit}, base=API_V3)
    except Exception as e:
        LOG.warning("get_order_book %s failed: %s", symbol, e)
        return None

async def get_klines(symbol: str, interval: str = "1d", limit: int = 200) -> Optional[List[List]]:
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        # Kline'lar da kısa TTL ile cache'lensin
        return await _get("/klines", params=params, base=API_V3, cache_ttl=20.0)
    except Exception as e:
        LOG.warning("get_klines %s failed: %s", symbol, e)
        return None

async def get_multiple_klines(symbols: List[str], interval: str = "1d", limit: int = 60, concurrency: int = 8) -> Dict[str, Optional[List[List]]]:
    sem = asyncio.Semaphore(concurrency)

    async def _one(sym: str):
        async with sem:
            return await get_klines(sym, interval=interval, limit=limit)

    tasks = [_one(s) for s in symbols]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    out: Dict[str, Optional[List[List]]] = {}
    for s, r in zip(symbols, res):
        out[s] = None if isinstance(r, Exception) else r
    return out

async def get_all_symbols() -> List[str]:
    try:
        data = await _get("/exchangeInfo", base=API_V3, cache_ttl=30.0)
        syms = [s.get("symbol") for s in data.get("symbols", []) if s.get("status") == "TRADING"]
        return sorted(list(set(syms)))
    except Exception as e:
        LOG.warning("get_all_symbols failed: %s", e)
        return []

async def exchange_info_details() -> Dict[str, Any]:
    try:
        data = await _get("/exchangeInfo", base=API_V3, cache_ttl=30.0)
        return {s.get("symbol"): s for s in data.get("symbols", [])}
    except Exception as e:
        LOG.warning("exchange_info_details failed: %s", e)
        return {}

# --------- Futures ----------
async def get_funding_rate(symbol: Optional[str] = None, limit: int = 100) -> Optional[Any]:
    try:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        # Bu endpoint FAPI'de /fapi/v1
        return await _get("/fapi/v1/fundingRate", params=params, base=FAPI_BASE, cache_ttl=10.0)
    except Exception as e:
        LOG.warning("get_funding_rate %s failed: %s", symbol, e)
        return None

async def get_open_interest(symbol: str) -> Optional[dict]:
    try:
        return await _get("/fapi/v1/openInterest", params={"symbol": symbol}, base=FAPI_BASE, cache_ttl=5.0)
    except Exception as e:
        LOG.warning("get_open_interest %s failed: %s", symbol, e)
        return None

# --------- Signed (Spot + Futures) ----------
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

# --------- WebSocket ----------
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

    async def kline(self, symbol: str, interval: str, limit: int = 200):
        return await get_klines(symbol, interval=interval, limit=limit)

    async def funding(self, symbol: Optional[str] = None, limit: int = 100):
        return await get_funding_rate(symbol=symbol, limit=limit)

    async def exchange_info(self):
        return await exchange_info_details()

    def start_combined(self, streams: List[str], handler: Callable[[dict], None]):
        return self.run_task(start_combined_stream(streams, handler))
        
