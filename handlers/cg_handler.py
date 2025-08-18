# handlers/cg_handler.py
import logging
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils.coinglass_utils import build_exchange_report

LOG = logging.getLogger("cg_handler")
LOG.addHandler(logging.NullHandler())


def cg_command(update: Update, context: CallbackContext) -> None:
    try:
        args = context.args
        symbol = args[0].upper() if args else "BTC"

        report = build_exchange_report(symbol)
        update.message.reply_text(report)

    except Exception as e:
        LOG.error(f"/cg command error: {e}")
        update.message.reply_text("❌ Coinglass raporu alınırken hata oluştu.")


def register(app):
    """Plugin loader uyumlu register"""
    app.add_handler(CommandHandler("cg", cg_command))
