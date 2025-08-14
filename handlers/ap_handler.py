#ap_handler.py
#ap

import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.ap_utils import (
    get_btc_dominance,
    get_altcoin_data,
    get_btc_data,
    calculate_ap_score
)

async def ap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ap komutu: AP skor raporu"""
    msg = await update.message.reply_text("AP skor raporu hazırlanıyor... ⏳")

    try:
        # Async metrikleri paralel al
        btc_dominance, alt_metrics, btc_metrics = await asyncio.gather(
            get_btc_dominance(),
            get_altcoin_data(),
            get_btc_data()
        )

        metrics = {
            "btc_dominance": btc_dominance,
            "alt": alt_metrics,
            "btc": btc_metrics
        }

        # AP skoru hesapla
        ap_score = calculate_ap_score(metrics)

        # Mesajı hazırla
        report = (
            f"📊 <b>AP Skor Raporu</b>\n\n"
            f"BTC Dominance: {btc_dominance:.2f}% (Score: {ap_score['btc_dominance_score']})\n\n"
            f"<b>Altcoin</b>\n"
            f"Fiyat değişimi: {alt_metrics.get('price_change', 0):.2f}% "
            f"(Score: {ap_score['alt_price_score']})\n"
            f"Net IO: {alt_metrics.get('net_io', 0):,} USD "
            f"(Score: {ap_score['alt_io_score']})\n\n"
            f"<b>BTC</b>\n"
            f"Fiyat değişimi: {btc_metrics.get('price_change', 0):.2f}% "
            f"(Score: {ap_score['btc_price_score']})\n"
            f"Net IO: {btc_metrics.get('net_io', 0):,} USD "
            f"(Score: {ap_score['btc_io_score']})\n\n"
            f"🔥 <b>Toplam AP Skoru:</b> {ap_score['total_score']}"
        )

        await msg.edit_text(report, parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Hata oluştu: {e}")

def register(application):
    """Plugin loader için register fonksiyonu."""
    application.add_handler(CommandHandler("ap", ap_handler))
