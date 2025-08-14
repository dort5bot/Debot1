# ♦️bootmaster (revize)
# Plugin loader uyumlu
# self-ping kaldırıldı, sadece keep_alive web server aktif

# main.py — Modern & Geliştirilebilir Telegram Trading Bot

import asyncio
import os
import logging
from telegram.ext import ApplicationBuilder

from keep_alive import keep_alive
from utils.db import init_db
from utils.signal_evaluator import SignalEvaluator
from utils.order_manager import OrderManager
from utils.binance_api import BinanceClient
from utils.stream_manager import StreamManager
from utils.monitoring import configure_logging
from utils.config import (
    STREAM_SYMBOLS,
    STREAM_INTERVAL,
    EVALUATOR_WINDOW,
    EVALUATOR_THRESHOLD,
    PAPER_MODE
)
from utils.handler_loader import load_handlers
from strategies.rsi_macd_strategy import RSI_MACD_Strategy

# -------------------------------
# Global Config & Init
configure_logging(logging.INFO)
LOG = logging.getLogger("main")

init_db()  # Database init

# Binance client & stream manager
bin_client = BinanceClient()
stream_mgr = StreamManager(bin_client)

# Order Manager
order_manager = OrderManager(paper_mode=PAPER_MODE)

# Signal evaluator
async def decision_cb(decision):
    return await order_manager.process_decision(decision)

evaluator = SignalEvaluator(
    decision_callback=decision_cb,
    window_seconds=EVALUATOR_WINDOW,
    threshold=EVALUATOR_THRESHOLD
)
evaluator.start()

# Shared queue for kline data
queue = asyncio.Queue()

# Strategies dictionary
strategies = {symbol: RSI_MACD_Strategy(symbol) for symbol in STREAM_SYMBOLS}


# -------------------------------
# Data bridge for WebSocket messages
async def bridge(msg):
    """Route WebSocket messages to appropriate handlers."""
    from handlers import funding_handler, ticker_handler

    try:
        data = msg.get("data") if isinstance(msg, dict) else msg
        if isinstance(data, dict) and "k" in data:
            await queue.put(data)  # Kline data
        else:
            await funding_handler.handle_funding_data(data)
            await ticker_handler.handle_ticker_data(data)
    except Exception as e:
        LOG.exception("bridge error: %s", e)


# -------------------------------
# Kline Processor
async def kline_processor():
    """Consume kline data and feed strategies."""
    from handlers import signal_handler

    while True:
        data = await queue.get()
        try:
            k = data.get("k", {})
            if not k.get("x"):  # Only closed candles
                continue
            close_price = float(k["c"])
            symbol = data.get("s")

            strategy = strategies.get(symbol)
            if strategy:
                signal = strategy.on_new_close(close_price)
                if signal:
                    await signal_handler.publish_signal(
                        "rsi_macd",
                        symbol,
                        signal["type"],
                        strength=signal["strength"],
                        payload=signal["payload"]
                    )
        except Exception as e:
            LOG.exception("kline_processor error: %s", e)
        finally:
            queue.task_done()


# -------------------------------
# Stream List Builder
def build_stream_list(symbols, interval):
    return [
        f"{s.lower()}@kline_{interval}" for s in symbols
    ] + [
        f"{s.lower()}@ticker" for s in symbols
    ]


# -------------------------------
# Start All Services
def start_all_services():
    streams = build_stream_list(STREAM_SYMBOLS, STREAM_INTERVAL)
    stream_mgr.start_combined_groups(streams, bridge)
    stream_mgr.start_periodic_funding_poll(
        STREAM_SYMBOLS, interval_sec=60,
        callback=lambda data: asyncio.create_task(
            __import__("handlers").funding_handler.handle_funding_data(data)
        )
    )
    asyncio.create_task(kline_processor())
    LOG.info("Started streams for: %s", ", ".join(STREAM_SYMBOLS))


# -------------------------------
# Main Entry Point
async def main():
    LOG.info("Starting bot. PAPER_MODE=%s", PAPER_MODE)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        LOG.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    # Telegram Application
    app = ApplicationBuilder().token(token).build()

    # Pass evaluator to signal handler dynamically
    from handlers import signal_handler
    signal_handler.set_evaluator(evaluator)

    # Load all handlers automatically
    load_handlers(app)

    # Start background services
    start_all_services()

    # Keep-alive web server
    keep_alive()

    # Run Telegram bot (blocking)
    await app.run_polling()


# -------------------------------
if __name__ == "__main__":
    asyncio.run(main())
 
