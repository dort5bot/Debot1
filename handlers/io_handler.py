# handlers/io_handler.py
import asyncio
import logging
from typing import Optional

#➡️
from telegram.ext import CommandHandler


from utils.io_utils import (
    market_inout,
    symbol_inout,
    format_market_report,
    format_symbol_report,
)

LOG = logging.getLogger("io_handler")
LOG.addHandler(logging.NullHandler())

COMMAND = "io"
HELP = "/io [SYMBOL] — Emir defteri/taker analizi ile piyasa-alış satışı ve nakit göçü raporu.\n" \
       "Ör: /io  |  /io ETHUSDT"

#♦️
def register(application):
    """
    Plugin loader'ın çağıracağı fonksiyon.
    """
    handler_info = get_handler()
    application.add_handler(CommandHandler(handler_info["command"], handler_info["callback"]))

#♦️



# --- MAIN Plugin Loader uyumlu arayüz ---
def get_handler():
    """
    Main plugin loader'ın çağıracağı metadata.
    Dönen yapı örn:
    {
      "command": "io",
      "callback": handle_command,
      "help": "..."
    }
    """
    return {
        "command": COMMAND,
        "callback": handle_command,
        "help": HELP,
    }

# --- Komut implementasyonu ---
async def handle_command(ctx, args: Optional[str] = None) -> str:
    """
    ctx: bot'un kendi context nesnesi (log, reply vb)
    args: kullanıcı argümanı (örn. "ETHUSDT")
    Dönüş: render edilecek metin
    """
    symbol = (args or "").strip().upper()
    try:
        if not symbol:
            # Piyasa geneli
            data = await market_inout()
            text = format_market_report(data)
        else:
            # Tek sembol
            data = await symbol_inout(symbol)
            text = format_symbol_report(data)

        # Alt yorum (risk değerlendirmesi)
        text += "\n\n"
        try:
            # Basit risk yorumu: 1d < 50 ise uzak dur
            if not symbol:
                r1d = (data.get("market_ratios") or {}).get("1d", 0.0)
            else:
                r1d = (data.get("ratios") or {}).get("1d", 0.0)
            if r1d < 50.0:
                text += "Piyasa günlük nakit giriş oranı bakımından riskli görünüyor. 1d alıcı oranı %50 üzerine çıkmadıkça temkinli ol."
            else:
                text += "Piyasa günlük nakit giriş oranı %50 üzerinde. Genel koşullar sert düşüş riskini azaltıyor; yine de risk yönetimi şart."
        except Exception:
            pass

        return text
    except Exception as e:
        LOG.exception("io command failed: %s", e)
        return "Üzgünüm, /io raporu oluşturulurken hata oluştu."
