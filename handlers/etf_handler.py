# handlers/etf_handler.py
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils import coinglass_utils as cg

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


async def etf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/etf komutu ile ETF raporu gönderir."""
    if not context.args:
        await update.message.reply_text("Kullanım: /etf BTC veya /etf ETH")
        return

    asset = context.args[0].upper()
    msg = await cg.parse_etf_report(asset)
    await update.message.reply_text(msg)


def register(application):
    """Plugin loader ile uyumlu register fonksiyonu."""
    handler = CommandHandler("etf", etf_command)
    application.add_handler(handler)
