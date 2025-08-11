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
