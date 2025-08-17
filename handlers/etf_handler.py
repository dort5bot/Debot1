###handlers/etf_handler.py

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.coinglass_utils import get_etf_flow
from asyncio import get_running_loop

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.addHandler(logging.StreamHandler())

# ---------------- HANDLER ---------------- #
async def etf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /etf komutu ile ETF net akış raporunu gönderir.
    Kullanım: /etf BTC veya /etf ETH
    """
    if not context.args:
        await update.message.reply_text("Kullanım: /etf BTC veya /etf ETH")
        return

    asset_arg = context.args[0].lower()
    asset_map = {
        "btc": "bitcoin",
        "eth": "ethereum"
    }
    asset = asset_map.get(asset_arg, asset_arg)

    await update.message.reply_text(f"⏳ {asset.upper()} ETF verileri alınıyor...")

    # requests tabanlı senkron fonksiyon -> async uyumlu
    loop = get_running_loop()
    msg = await loop.run_in_executor(None, get_etf_flow, asset)

    await update.message.reply_text(msg)


def register(application):
    """Plugin loader ile uyumlu register fonksiyonu."""
    handler = CommandHandler("etf", etf_command)
    application.add_handler(handler)
