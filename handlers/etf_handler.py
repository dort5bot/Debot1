# handlers/etf_handler.py

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from utils.coinglass_utils import parse_etf_report

LOG = logging.getLogger("etf_handler")

async def etf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """BTC ve ETH ETF raporlarını gönderir."""
    try:
        await update.message.reply_text("⏳ ETF verileri alınıyor...")

        btc_report = await parse_etf_report("BTC")
        eth_report = await parse_etf_report("ETH")

        msg = f"{btc_report}\n\n{eth_report}"
        await update.message.reply_text(msg)
    except Exception as e:
        LOG.exception("ETF raporu hazırlanırken hata oluştu: %s", e)
        await update.message.reply_text("⚠ ETF verisi alınamadı.")

def register(application):
    """Plugin loader uyumlu register fonksiyonu."""
    application.add_handler(CommandHandler("etf", etf_command))
