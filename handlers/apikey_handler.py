#apikey-handler
from telegram import Update
from telegram.ext import ContextTypes
from utils.apikey_utils import add_or_update_apikey, get_apikey

async def apikey_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        key = get_apikey(user_id)
        if key:
            await update.message.reply_text(f"✅ Kayıtlı API Key'iniz: {key[:4]}****")
        else:
            await update.message.reply_text("❌ Henüz API key kayıtlı değil. /apikey <key> komutu ile ekleyin.")
        return

    api_key = args[0]
    add_or_update_apikey(user_id, api_key)
    await update.message.reply_text("✅ API key başarıyla kaydedildi/güncellendi.")


##
from telegram import Update
from telegram.ext import ContextTypes
from utils.apikey_utils import set_user_apikey, get_user_apikey

async def apikey_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        current_key = get_user_apikey(user_id)
        if current_key:
            await update.message.reply_text("🔑 Mevcut API anahtarınız kayıtlı.")
        else:
            await update.message.reply_text("❌ Henüz API anahtarı kaydedilmemiş.")
        return

    new_apikey = context.args[0]
    set_user_apikey(user_id, new_apikey)
    await update.message.reply_text("✅ API anahtarınız güncellendi.")
    
