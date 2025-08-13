#♦️bootmaster
#plugin loaderuyumlu

import asyncio
import os
import logging
from telegram.ext import ApplicationBuilder
from keep_alive import keep_alive

# Utils
from utils.db import init_db
from utils.signal_evaluator import SignalEvaluator
from utils.order_manager import OrderManager
from utils.binance_api import BinanceClient
from utils.stream_manager import StreamManager
from utils.monitoring import configure_logging
from utils.config import STREAM_SYMBOLS, STREAM_INTERVAL, EVALUATOR_WINDOW, EVALUATOR_THRESHOLD, PAPER_MODE
from utils.handler_loader import load_handlers

# Handlers ve strategies
from handlers import signal_handler, kline_handler, ticker_handler, alerts_handler
from strategies.rsi_macd_strategy import RSI_MACD_Strategy

# -------------------------------
# Logging ve DB
configure_logging(logging.INFO)
LOG = logging.getLogger("main")
init_db()

# -------------------------------
# Event loop
loop = asyncio.get_event_loop()

# Binance client & stream manager
bin_client = BinanceClient()
stream_mgr = StreamManager(bin_client, loop=loop)

# Order manager & evaluator
om = OrderManager(paper_mode=PAPER_MODE)

async def decision_cb(decision):
    return await om.process_decision(decision)

evaluator = SignalEvaluator(
    decision_callback=decision_cb,
    loop=loop,
    window_seconds=EVALUATOR_WINDOW,
    threshold=EVALUATOR_THRESHOLD
)
evaluator.start()
signal_handler.set_evaluator(evaluator)

# Shared kline queue & strategies
queue = asyncio.Queue()
strategies = {s: RSI_MACD_Strategy(s) for s in STREAM_SYMBOLS}

# WebSocket köprüsü
async def bridge(msg):
    try:
        data = msg.get("data") if isinstance(msg, dict) and "data" in msg else msg
        if isinstance(data, dict) and "k" in data:
            await queue.put(data)
        else:
            await funding_handler.handle_funding_data(data)
            await ticker_handler.handle_ticker_data(data)
    except Exception as e:
        LOG.exception("bridge error: %s", e)

# Kline processor
async def kline_processor():
    while True:
        data = await queue.get()
        try:
            s = data.get("s")
            k = data.get("k", {})
            if not k.get("x", False):
                continue
            close = float(k.get("c"))
            st = strategies.get(s)
            if st:
                out = st.on_new_close(close)
                if out:
                    await signal_handler.publish_signal(
                        "rsi_macd", s, out["type"], strength=out["strength"], payload=out["payload"]
                    )
        except Exception as e:
            LOG.exception("kline_processor error: %s", e)
        finally:
            queue.task_done()

# Stream listesi
def build_stream_list(symbols, interval):
    streams = []
    for s in symbols:
        streams.append(f"{s.lower()}@kline_{interval}")
        streams.append(f"{s.lower()}@ticker")
    return streams

# Tüm servisleri başlat
def start_all_services():
    streams = build_stream_list(STREAM_SYMBOLS, STREAM_INTERVAL)
    stream_mgr.start_combined_groups(streams, bridge)
    stream_mgr.start_periodic_funding_poll(
        STREAM_SYMBOLS, interval_sec=60, callback=funding_handler.handle_funding_data
    )
    loop.create_task(kline_processor())
    LOG.info("Started streams for symbols: %s", STREAM_SYMBOLS)

# -------------------------------
# Telegram bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    LOG.error("TELEGRAM_BOT_TOKEN environment variable not set!")
    exit(1)

application = ApplicationBuilder().token(TOKEN).build()

# Plugin loader ile tüm handlerları yükle
load_handlers(application)

# -------------------------------
# Ana çalıştırma
if __name__ == "__main__":
    LOG.info("Starting bot. PAPER_MODE=%s", PAPER_MODE)
    keep_alive()
    start_all_services()
    loop.create_task(application.run_polling())
    loop.run_forever()
