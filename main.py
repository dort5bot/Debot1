#main.py
# main.py
import asyncio
import os
import logging
from utils.db import init_db
from utils.signal_evaluator import SignalEvaluator
from utils.order_manager import OrderManager
from utils.binance_api import BinanceClient
from handlers import signal_handler, kline_handler, funding_handler, ticker_handler
from collections import deque

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("main")

# init DB
init_db()

# bootstrap
loop = asyncio.get_event_loop()
bin_client = BinanceClient()

# create order manager and evaluator
om = OrderManager(paper_mode=(os.getenv("PAPER_MODE","true").lower() in ("1","true","yes")))
async def decision_callback(decision):
    return await om.process_decision(decision)

evaluator = SignalEvaluator(decision_callback=decision_callback, loop=loop, window_seconds=12, threshold=0.25)
evaluator.start()
signal_handler.set_evaluator(evaluator)

# create queue shared by kline workers
queue = asyncio.Queue()

# ws bridge - pushes combined stream messages into queue or calls handlers
async def ws_bridge(streams):
    async def bridge(msg):
        # combined messages look like: {"stream":"...","data":{...}}
        data = msg.get("data") if isinstance(msg, dict) and "data" in msg else msg
        # dispatch to ticker/funding if stream names included
        # For kline streams we push to queue
        # Here we keep it simple: if 'k' in data -> kline payload
        if isinstance(data, dict) and "k" in data:
            await queue.put(data)
        else:
            # try funding / ticker handlers
            # spawn handler tasks if async
            await funding_handler.handle_funding_data(data)
            await ticker_handler.handle_ticker_data(data)
    await bin_client.start_combined(streams, bridge)

def build_streams(symbols, interval):
    streams = []
    for s in symbols:
        streams.append(f"{s.lower()}@kline_{interval}")
        # also optionally add funding and ticker
        streams.append(f"{s.lower()}@ticker")
        # futures funding rate is not available as websocket stream name in this simple combined approach,
        # we can pull via REST periodically instead.
    return streams

def start_workers_and_ws():
    symbols = [s.strip().upper() for s in os.getenv("STREAM_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")]
    interval = os.getenv("STREAM_INTERVAL", "1m")
    streams = build_streams(symbols, interval)
    loop.create_task(ws_bridge(streams))
    # start kline workers
    for s in symbols:
        loop.create_task(kline_handler.kline_worker(queue, s, interval))

if __name__ == "__main__":
    print("Starting bot. PAPER_MODE =", om.paper_mode)
    start_workers_and_ws()
    loop.run_forever()
