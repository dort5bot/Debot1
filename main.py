#♦️bootmaster 
# main.py
import asyncio
import os
import logging
from utils.db import init_db
from utils.signal_evaluator import SignalEvaluator
from utils.order_manager import OrderManager
from utils.binance_api import BinanceClient
from utils.stream_manager import StreamManager
from utils.monitoring import configure_logging, telegram_alert
from utils.config import STREAM_SYMBOLS, STREAM_INTERVAL, EVALUATOR_WINDOW, EVALUATOR_THRESHOLD, PAPER_MODE
from handlers import signal_handler, kline_handler, funding_handler, ticker_handler
from handlers import alerts_handler
from strategies.rsi_macd_strategy import RSI_MACD_Strategy

# configure logging
configure_logging(logging.INFO)
LOG = logging.getLogger("main")

# init DB
init_db()

# event loop
loop = asyncio.get_event_loop()

# Binance client & stream manager
bin_client = BinanceClient()
stream_mgr = StreamManager(bin_client, loop=loop)

# Order manager & evaluator
om = OrderManager(paper_mode=PAPER_MODE)
async def decision_cb(decision):
    # risk manager check could be added here (not shown)
    return await om.process_decision(decision)

evaluator = SignalEvaluator(decision_callback=decision_cb, loop=loop, window_seconds=EVALUATOR_WINDOW, threshold=EVALUATOR_THRESHOLD)
evaluator.start()
signal_handler.set_evaluator(evaluator)

# shared kline queue
queue = asyncio.Queue()

# instantiate per-symbol strategy instances
strategies = { s: RSI_MACD_Strategy(s) for s in STREAM_SYMBOLS }

# bridge: receives combined ws messages and routes
async def bridge(msg):
    data = msg.get("data") if isinstance(msg, dict) and "data" in msg else msg
    # kline payload?
    if isinstance(data, dict) and "k" in data:
        # push to queue for workers
        await queue.put(data)
    else:
        # funding / ticker fallback via REST or combined streams
        await funding_handler.handle_funding_data(data)
        await ticker_handler.handle_ticker_data(data)

# process closed klines from queue with strategy & publish
async def kline_processor():
    while True:
        data = await queue.get()
        try:
            s = data.get("s")
            k = data.get("k", {})
            if not k.get("x", False):
                queue.task_done()
                continue
            close = float(k.get("c"))
            # feed strategy
            st = strategies.get(s)
            if st:
                out = st.on_new_close(close)
                if out:
                    # publish via signal handler
                    await signal_handler.publish_signal("rsi_macd", s, out["type"], strength=out["strength"], payload=out["payload"])
        except Exception as e:
            LOG.exception("kline_processor error: %s", e)
        finally:
            queue.task_done()

def build_stream_list(symbols, interval):
    streams = []
    for s in symbols:
        streams.append(f"{s.lower()}@kline_{interval}")
        streams.append(f"{s.lower()}@ticker")
        # funding via REST poll handled by stream_mgr
    return streams

def start_all():
    streams = build_stream_list(STREAM_SYMBOLS, STREAM_INTERVAL)
    stream_mgr.start_combined_groups(streams, bridge)
    # start periodic funding poll (every 60s)
    stream_mgr.start_periodic_funding_poll(STREAM_SYMBOLS, interval_sec=60, callback=funding_handler.handle_funding_data)
    # start local kline processor
    loop.create_task(kline_processor())
    LOG.info("Started streams for symbols: %s", STREAM_SYMBOLS)

if __name__ == "__main__":
    LOG.info("Starting bot. PAPER_MODE=%s", PAPER_MODE)
    start_all()
    loop.run_forever()



###
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers.apikey_handler import apikey_handler
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app = ApplicationBuilder().token(TOKEN).build()

# Komutlar
app.add_handler(CommandHandler("apikey", apikey_handler))

if __name__ == "__main__":
    app.run_polling()
