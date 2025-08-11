#apikey-handler

from telegram import Update
from telegram.ext import ContextTypes
from utils.apikey_utils import add_or_update_apikey, get_apikey, set_alarm_settings, set_trade_settings

# /apikey KOMUTU
async def apikey_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Kullanım: /apikey <API_KEY>")
        return

    api_key = context.args[0]
    add_or_update_apikey(update.effective_user.id, api_key)
    await update.message.reply_text("✅ API Key kaydedildi.")

# /setalarm KOMUTU
async def set_alarm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Kullanım: /setalarm <alarm_ayarı>")
        return

    settings = " ".join(context.args)
    set_alarm_settings(update.effective_user.id, settings)
    await update.message.reply_text(f"⏰ Alarm ayarınız kaydedildi: {settings}")

# /settrade KOMUTU
async def set_trade_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Kullanım: /settrade <trade_ayarı>")
        return

    settings = " ".join(context.args)
    set_trade_settings(update.effective_user.id, settings)
    await update.message.reply_text(f"💹 Trade ayarınız kaydedildi: {settings}")
    
