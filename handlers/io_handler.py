# handlers/io_handler.py
import logging
from typing import Optional

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from utils.io_utils import (
    market_inout,
    symbol_inout,
    format_market_report,
    format_symbol_report,
)

LOG = logging.getLogger("io_handler")
LOG.addHandler(logging.NullHandler())

COMMAND = "io"
HELP = (
    "/io [SYMBOL] — Emir defteri/taker analizi ile piyasa-alış satışı ve nakit göçü raporu.\n"
    "Ör: /io  |  /io ETHUSDT"
)


# ---------------- Plugin loader uyumlu register ----------------
def register(application):
    """
    Plugin loader'ın çağıracağı fonksiyon.
    """
    handler_info = get_handler()
    application.add_handler(
        CommandHandler(handler_info["command"], handler_info["callback"])
    )


def get_handler():
    """
    Main plugin loader'ın çağıracağı metadata.
    """
    return {
        "command": COMMAND,
        "callback": handle_command,
        "help": HELP,
    }


# ---------------- Komut implementasyonu ----------------
async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /io komutu çalıştırıldığında tetiklenir.
    update: Telegram Update nesnesi
    context: Bot context, args context.args içinde gelir
    """
    args = " ".join(context.args) if context.args else None
    symbol = (args or "").strip().upper()

    try:
        # Piyasa geneli veya tek sembol
        if not symbol:
            data = await market_inout()
            text = format_market_report(data)
        else:
            data = await symbol_inout(symbol)
            text = format_symbol_report(data)

        # Alt yorum (risk değerlendirmesi)
        try:
            if not symbol:
                r1d = (data.get("market_ratios") or {}).get("1d", 0.0)
            else:
                r1d = (data.get("ratios") or {}).get("1d", 0.0)

            if r1d < 50.0:
                text += "\n\nPiyasa günlük nakit giriş oranı bakımından riskli görünüyor. 1d alıcı oranı %50 üzerine çıkmadıkça temkinli ol."
            else:
                text += "\n\nPiyasa günlük nakit giriş oranı %50 üzerinde. Genel koşullar sert düşüş riskini azaltıyor; yine de risk yönetimi şart."
        except Exception as e:
            LOG.warning("Alt yorum hesaplanamadı: %s", e)

        await update.message.reply_text(text)
    except Exception as e:
        LOG.exception("io command failed: %s", e)
        await update.message.reply_text("Üzgünüm, /io raporu oluşturulurken hata oluştu.")
