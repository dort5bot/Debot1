# handlers/ap_handler.py
import math
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils import ap_utils


async def ap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- Metrikleri topla ---
    metrics = await ap_utils.collect_ap_metrics()
    scores = ap_utils.calculate_ap_score(metrics)

    # --- Skorları 0-100 ölçeğine çevir ---
    # Altların BTC'ye karşı kısa vade gücü -> btc_dominance_score + alt_price_score
    alt_vs_btc_score = scores["btc_dominance_score"] + scores["alt_price_score"]
    alt_vs_btc_pct = round(((alt_vs_btc_score + 4) / 8) * 100, 1)  # max 4, min -4

    # Altların USD bazlı kısa vade gücü -> alt_price_score + alt_io_score
    alt_usd_score = scores["alt_price_score"] + scores["alt_io_score"]
    alt_usd_pct = round(((alt_usd_score + 4) / 8) * 100, 1)

    # Uzun vade güç -> total_score (max 10, min -10)
    long_term_pct = round(((scores["total_score"] + 10) / 20) * 100, 1)

    # --- Yorum ---
    def yorum(pct):
        if pct < 20:
            return "Çok zayıf"
        elif pct < 40:
            return "Zayıf"
        elif pct < 60:
            return "Orta seviye"
        elif pct < 80:
            return "Güçlü"
        else:
            return "Çok güçlü"

    yorum_text = (
        f"({alt_vs_btc_pct}): BTC karşısında {yorum(alt_vs_btc_pct).lower()} performans.\n"
        f"({alt_usd_pct}): USD bazlı kısa vade genel altcoin gücü.\n"
        f"({long_term_pct}): {yorum(long_term_pct)} uzun vade alıcı baskısı."
    )

    # --- Mesaj ---
    msg = (
        f"📊 *AP Raporu*\n\n"
        f"Altların Kısa Vadede BTC'ye Karşı Gücü (0-100): *{alt_vs_btc_pct}*\n"
        f"Altların Kısa Vadede Gücü (0-100): *{alt_usd_pct}*\n"
        f"Coinlerin Uzun Vadede Gücü (0-100): *{long_term_pct}*\n\n"
        f"*Yorum:*\n{yorum_text}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


# Plugin loader uyumlu kayıt
def register(application):
    application.add_handler(CommandHandler("ap", ap_handler))
