# handlers/io_handler.py
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils.io_utils import build_io_snapshot
from utils.binance_api import get_binance_api
from utils.config import CONFIG
import asyncio

async def fetch_symbol_snapshot(symbol: str) -> dict:
    api = get_binance_api()
    try:
        klines, order_book, trades, ticker, funding = await asyncio.gather(
            api.get_klines(symbol, interval="1m", limit=CONFIG.IO.RSI_PERIOD + 1),
            api.get_order_book(symbol, limit=100),
            api.get_recent_trades(symbol, limit=500),
            api.get_24h_ticker(symbol),
            api.get_funding_rate(symbol, limit=1)
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
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "price": "0", "mts_score": 0, "trend_score": 0}

async def io_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Lütfen en az bir sembol girin, örn: /io BTC ETH BNB")
        return

    # Sembolleri normalize et, USDT ekle
    symbols = []
    for s in args:
        s_clean = s.upper()
        if not s_clean.endswith("USDT") and len(s_clean) <= 5:
            s_clean += "USDT"
        symbols.append(s_clean)

    # Çoklu sembol snapshot
    snapshots = await asyncio.gather(*[fetch_symbol_snapshot(sym) for sym in symbols])

    # Mesajı hazırla
    msg_lines = []
    for snap in snapshots:
        if snap.get("error"):
            msg_lines.append(f"*{snap['symbol']}* - Veri çekilemedi: {snap['error']}\n")
        else:
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

    await update.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")

def register(app):
    app.add_handler(CommandHandler("io", io_command))
