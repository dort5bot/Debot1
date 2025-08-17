# handlers/etf_handler.py
import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from utils.coinglass_utils import get_etf_flow

LOG = logging.getLogger("etf_handler")
LOG.addHandler(logging.NullHandler())

COMMAND = "etf"
HELP = "/etf [btc|eth] — Belirtilen coin için ETF net akış raporu gösterir."

async def etf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /etf komutu handler'ı.
    Kullanım: /etf btc veya /etf eth
    """
    if not context.args:
        await update.message.reply_text("Lütfen bir varlık belirtin: btc veya eth\nÖrnek: /etf btc")
        return

    asset_input = context.args[0].lower()
    if asset_input not in ["btc", "eth"]:
        await update.message.reply_text("Desteklenen varlıklar: btc, eth")
        return

    asset_map = {"btc": "bitcoin", "eth": "ethereum"}
    asset = asset_map[asset_input]

    await update.message.reply_text(f"{asset.upper()} için ETF verileri alınıyor... ⏳")

    report = get_etf_flow(asset)
    await update.message.reply_text(report)

# ---------------- Handler kaydı ---------------- #
def register(application):
    application.add_handler(CommandHandler(COMMAND, etf_command))
