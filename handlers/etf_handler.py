## etf handler

from telegram import Update
from telegram.ext import ContextTypes
from utils.coinglass_utils import parse_etf_report

async def etf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        btc_report = parse_etf_report("bitcoin")
        eth_report = parse_etf_report("ethereum")
        final_report = f"{btc_report}\n\n{eth_report}"
        await update.message.reply_text(final_report)
    except Exception as e:
        await update.message.reply_text(f"Hata oluştu: {e}")
