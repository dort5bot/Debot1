# handlers/io_handler.py
import asyncio
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils.io_utils import build_io_snapshot
from utils.binance_api import get_binance_api

async def fetch_symbol_snapshot(symbol: str) -> dict:
    api = get_binance_api()

    # Verileri eş zamanlı çek
    klines_task = api.get_klines(symbol, interval="1m", limit=CONFIG.IO.RSI_PERIOD + 1)
    order_book_task = api.get_order_book(symbol, limit=100)
    trades_task = api.get_recent_trades(symbol, limit=500)
    ticker_task = api.get_24h_ticker(symbol)
    funding_task = api.get_funding_rate(symbol, limit=1)

    klines, order_book, trades, ticker, funding = await asyncio.gather(
        klines_task, order_book_task, trades_task, ticker_task, funding_task
    )

    # Snapshot oluştur
    snapshot = build_io_snapshot(
        symbol=symbol,
        klines=klines,
        order_book=order_book,
        trades=trades,
        ticker=ticker,
        funding=funding[0] if funding else {"fundingRate": 0},
        oi=None,
        liquidations=None,
        with_cashflow=False
    )

    return snapshot

def io_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        update.message.reply_text("Lütfen bir sembol girin, örn: /io BTCUSDT")
        return

    symbol = args[0].upper()

    # Async snapshot fetch
    snapshot = asyncio.run(fetch_symbol_snapshot(symbol))

    price = snapshot.get("ticker", {}).get("lastPrice", "0")
    mts = snapshot.get("mts_score", 0)
    trend = snapshot.get("trend_score", 0)

    msg = (
        f"*{symbol} Snapshot*\n"
        f"Fiyat: {price}\n"
        f"MTS Skoru: {mts:.4f}\n"
        f"Trend Skoru: {trend:.4f}"
    )

    update.message.reply_text(msg, parse_mode="Markdown")

def register(app):
    app.add_handler(CommandHandler("io", io_command))
