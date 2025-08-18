#
# cg_handler.py
import asyncio
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils.coinglass_utils import get_etf_flow

async def cg_command(update: Update, context: CallbackContext):
    """
    /cg komutu: CoinGlass ETF net akış raporu
    """
    msg = "ETF verileri çekiliyor..."
    sent_msg = await update.message.reply_text(msg)

    loop = asyncio.get_event_loop()
    # Bitcoin ETF raporu
    btc_report = await loop.run_in_executor(None, get_etf_flow, "bitcoin")
    # Ethereum ETF raporu
    eth_report = await loop.run_in_executor(None, get_etf_flow, "ethereum")

    final_msg = f"💹 CoinGlass ETF Raporu\n\n{btc_report}\n\n{eth_report}"
    await sent_msg.edit_text(final_msg)


def register(dispatcher):
    """
    Bot dispatcher'a handler ekler
    """
    dispatcher.add_handler(CommandHandler("cg", cg_command))
