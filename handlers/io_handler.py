# handlers/io_handler.py
# handlers/io_handler.py
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils.io_utils import build_io_snapshot
from utils.binance_api import get_binance_api
from utils.config import CONFIG

async def fetch_symbol_snapshot(symbol: str) -> dict:
    """
    Tek bir sembol için Binance verilerini çekip snapshot oluşturur.
    """
    api = get_binance_api()

    klines_task = api.get_klines(symbol, interval="1m", limit=CONFIG.IO.RSI_PERIOD + 1)
    order_book_task = api.get_order_book(symbol, limit=100)
    trades_task = api.get_recent_trades(symbol, limit=500)
    ticker_task = api.get_24h_ticker(symbol)
    funding_task = api.get_funding_rate(symbol, limit=1)

    klines, order_book, trades, ticker, funding = await asyncio.gather(
        klines_task, order_book_task, trades_task, ticker_task, funding_task
    )

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

    snapshot["price"] = ticker.get("lastPrice", "0")
    return snapshot

async def io_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /io BTC ETH BNB gibi çoklu sembol komutunu işler
    """
    args = context.args
    if not args:
        await update.message.reply_text("Lütfen en az bir sembol girin, örn: /io BTC ETH BNB")
        return

    # Sembolleri normalize et, USDT ekle
    symbols = []
    for s in args:
        s_clean = s.upper()
        if len(s_clean) <= 5:
            s_clean += "USDT"
        symbols.append(s_clean)

    # Çoklu sembol snapshot fetch
    snapshots = await asyncio.gather(*[fetch_symbol_snapshot(sym) for sym in symbols])

    # Mesajı hazırla
    msg_lines = []
    for snap in snapshots:
        sym = snap.get("symbol", "")
        price = snap.get("price", "0")
        mts = snap.get("mts_score", 0)
        trend = snap.get("trend_score", 0)
        msg_lines.append(
            f"*{sym} Snapshot*\n"
            f"Fiyat: {price}\n"
            f"MTS Skoru: {mts:.4f}\n"
            f"Trend Skoru: {trend:.4f}\n"
        )

    msg = "\n".join(msg_lines)
    await update.message.reply_text(msg, parse_mode="Markdown")

def register(app):
    app.add_handler(CommandHandler("io", io_command))
