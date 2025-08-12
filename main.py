#♦️bootmaster 
# main.py
import asyncio
import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from keep_alive import keep_alive

from utils.db import init_db
from utils.signal_evaluator import SignalEvaluator
from utils.order_manager import OrderManager
from utils.binance_api import BinanceClient
from utils.stream_manager import StreamManager
from utils.monitoring import configure_logging
from utils.config import STREAM_SYMBOLS, STREAM_INTERVAL, EVALUATOR_WINDOW, EVALUATOR_THRESHOLD, PAPER_MODE
from handlers import signal_handler, kline_handler, funding_handler, ticker_handler
from handlers import alerts_handler
from handlers.apikey_handler import apikey_handler
from strategies.rsi_macd_strategy import RSI_MACD_Strategy
#🟧
from handlers import funding_handler
#
from handlers.etf_handler import etf_handler

#⏩ komut bolumu
# /f komutu
async def cmd_funding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args if context.args else []
    report = await funding_handler.funding_report(symbols=args if args else None)
    await update.message.reply_text(report)




                                    
# Logging ayarı
configure_logging(logging.INFO)
LOG = logging.getLogger("main")

# DB başlat
init_db()

# Event loop
loop = asyncio.get_event_loop()

# Binance client & stream manager
bin_client = BinanceClient()
stream_mgr = StreamManager(bin_client, loop=loop)

# Order manager & evaluator
om = OrderManager(paper_mode=PAPER_MODE)
async def decision_cb(decision):
    return await om.process_decision(decision)

evaluator = SignalEvaluator(decision_callback=decision_cb, loop=loop, window_seconds=EVALUATOR_WINDOW, threshold=EVALUATOR_THRESHOLD)
evaluator.start()
signal_handler.set_evaluator(evaluator)

# Shared kline queue
queue = asyncio.Queue()

# Strateji
strategies = {s: RSI_MACD_Strategy(s) for s in STREAM_SYMBOLS}

# WebSocket köprüsü
async def bridge(msg):
    data = msg.get("data") if isinstance(msg, dict) and "data" in msg else msg
    if isinstance(data, dict) and "k" in data:
        await queue.put(data)
    else:
        await funding_handler.handle_funding_data(data)
        await ticker_handler.handle_ticker_data(data)

# Kline işleyici
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
def start_all():
    streams = build_stream_list(STREAM_SYMBOLS, STREAM_INTERVAL)
    stream_mgr.start_combined_groups(streams, bridge)
    stream_mgr.start_periodic_funding_poll(STREAM_SYMBOLS, interval_sec=60, callback=funding_handler.handle_funding_data)
    loop.create_task(kline_processor())
    LOG.info("Started streams for symbols: %s", STREAM_SYMBOLS)


# Telegram bot(aplikasyon builder)✅🟥
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("apikey", apikey_handler))
app.add_handler(CommandHandler("etf", etf_handler))
app.add_handler(CommandHandler(["f", "F"], cmd_funding))




# ✅ Ana çalıştırma
if __name__ == "__main__":
    LOG.info("Starting bot. PAPER_MODE=%s", PAPER_MODE)
    keep_alive()  # Web sunucusunu aç
    start_all()
    loop.create_task(app.run_polling())
    loop.run_forever()
    #son. 🟥
    
