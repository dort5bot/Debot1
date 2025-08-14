# handlers/ap_handler.py
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.ap_utils import get_btc_dominance, calculate_ap_score
from utils.ap_utils import get_alt_metrics, get_btc_metrics  # async metrikler

async def ap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ap komutu: AP skor raporu"""
    msg = await update.message.reply_text("AP skor raporu hazırlanıyor... ⏳")

    try:
        # Async metrikleri al
        btc_dom_task = asyncio.create_task(get_btc_dominance())
        alt_task = asyncio.create_task(get_alt_metrics())
        btc_task = asyncio.create_task(get_btc_metrics())
        
        btc_dominance = await btc_dom_task
        alt_metrics = await alt_task
        btc_metrics = await btc_task

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
            f"Fiyat değişimi: {alt_metrics['price_change']:.2f}% (Score: {ap_score['alt_price_score']})\n"
            f"Net IO: {alt_metrics['net_io']:,} USD (Score: {ap_score['alt_io_score']})\n\n"
            f"<b>BTC</b>\n"
            f"Fiyat değişimi: {btc_metrics['price_change']:.2f}% (Score: {ap_score['btc_price_score']})\n"
            f"Net IO: {btc_metrics['net_io']:,} USD (Score: {ap_score['btc_io_score']})\n\n"
            f"🔥 <b>Toplam AP Skoru:</b> {ap_score['total_score']}"
        )

        await msg.edit_text(report, parse_mode="HTML")
    except Exception as e:
        await msg.edit_text(f"❌ Hata oluştu: {e}")


def register(application):
    """
    Plugin loader için register fonksiyonu.
    Uygulama başlatıldığında bu fonksiyon çağrılır ve komut eklenir.
    """
    application.add_handler(CommandHandler("ap", ap_handler))
