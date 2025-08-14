# handlers/apikey_handler.py
# API Key ve kullanıcı ayarları yönetimi
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from utils.apikey_utils import (
    add_or_update_apikey,
    get_apikey,
    set_alarm_settings,
    set_trade_settings
)

LOG = logging.getLogger("apikey_handler")
LOG.addHandler(logging.NullHandler())

COMMANDS = {
    "apikey": "/apikey <API_KEY> — API anahtarınızı kaydeder veya günceller.",
    "setalarm": "/setalarm <ayar> — Alarm ayarınızı kaydeder.",
    "settrade": "/settrade <ayar> — Trade ayarınızı kaydeder."
}


async def apikey_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının API key'ini kaydeder veya günceller"""
    if len(context.args) != 1:
        await update.message.reply_text(COMMANDS["apikey"])
        return

    api_key = context.args[0]
    add_or_update_apikey(update.effective_user.id, api_key)
    LOG.info(f"API key kaydedildi | user_id={update.effective_user.id}")
    await update.message.reply_text("✅ API Key başarıyla kaydedildi.")


async def setalarm_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının alarm ayarlarını kaydeder"""
    if not context.args:
        await update.message.reply_text(COMMANDS["setalarm"])
        return

    settings = " ".join(context.args)
    set_alarm_settings(update.effective_user.id, settings)
    LOG.info(f"Alarm ayarı kaydedildi | user_id={update.effective_user.id}, settings={settings}")
    await update.message.reply_text(f"⏰ Alarm ayarınız kaydedildi: {settings}")


async def settrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcının trade ayarlarını kaydeder"""
    if not context.args:
        await update.message.reply_text(COMMANDS["settrade"])
        return

    settings = " ".join(context.args)
    set_trade_settings(update.effective_user.id, settings)
    LOG.info(f"Trade ayarı kaydedildi | user_id={update.effective_user.id}, settings={settings}")
    await update.message.reply_text(f"💹 Trade ayarınız kaydedildi: {settings}")


def register(application):
    """Plugin loader için komut kayıt fonksiyonu"""
    application.add_handler(CommandHandler("apikey", apikey_cmd))
    application.add_handler(CommandHandler("setalarm", setalarm_cmd))
    application.add_handler(CommandHandler("settrade", settrade_cmd))
    
