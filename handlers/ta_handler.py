# handlers/ta_handler.py

import asyncio
import pandas as pd
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from utils.binance_api import get_binance_api
from utils.config import CONFIG
from utils.ta_utils import alpha_signal, scan_market


# ------------------------------------------------------------
# Yardımcı: Binance OHLCV -> DataFrame dönüştür
# ------------------------------------------------------------
async def fetch_ohlcv(symbol: str, hours: int = 4, interval: str = "1h") -> pd.DataFrame:
    client = get_binance_api()
    limit = hours * 60 // int(interval[:-1]) if interval.endswith("m") else hours
    kl = await client.get_klines(symbol, interval=interval, limit=limit)
    df = pd.DataFrame(
        kl,
        columns=["open_time","open","high","low","close","volume",
                 "close_time","qav","trades","taker_base","taker_quote","ignore"]
    )
    df = df.astype({
        "open": float, "high": float, "low": float,
        "close": float, "volume": float
    })
    return df


# ------------------------------------------------------------
# Komut handler
# ------------------------------------------------------------
def ta_handler(update: Update, context: CallbackContext) -> None:
    args = context.args
    chat_id = update.effective_chat.id

    async def _run():
        try:
            if len(args) == 0:
                # 📊 Market taraması
                api = get_binance_api()
                symbols = CONFIG.BINANCE.TOP_SYMBOLS_FOR_IO
                data = {}
                for sym in symbols:
                    df = await fetch_ohlcv(sym, hours=4, interval="1h")
                    data[sym] = df
                btc_ref = data.get("BTCUSDT", None)
                ref_close = btc_ref["close"] if btc_ref is not None else None
                results = scan_market(data, ref_close=ref_close)

                text = "📊 Market Scan (4h)\n"
                for sym, res in results.items():
                    score = res.get("score", res.get("alpha_ta", {}).get("score", 0))
                    signal = res.get("signal", res.get("alpha_ta", {}).get("signal", 0))
                    regime = res.get("detail", {}).get("regime_score", 0.0)

                    sig_txt = "LONG" if signal == 1 else ("SHORT" if signal == -1 else "FLAT")
                    text += f"{sym} → α: {round(score,2)} ({sig_txt}), Rejim: {round(regime,2)}\n"

                await context.bot.send_message(chat_id=chat_id, text=text)

            else:
                # Tek coin analizi
                coin = args[0].upper() + "USDT" if not args[0].endswith("USDT") else args[0].upper()
                hours = int(args[1]) if len(args) > 1 else 4
                interval = "1h"

                df = await fetch_ohlcv(coin, hours=hours, interval=interval)
                btc_df = await fetch_ohlcv("BTCUSDT", hours=hours, interval=interval)
                ref_close = btc_df["close"] if btc_df is not None else None

                res = alpha_signal(df, ref_series=ref_close)

                score = res["score"]
                sig = res["signal"]
                sig_txt = "LONG" if sig == 1 else ("SHORT" if sig == -1 else "FLAT")
                regime = res["detail"].get("regime_score", 0.0)

                entropy = res["detail"].get("entropy_score", 0.0)
                kalman = res["detail"].get("kalman_score", 0.0)
                leadlag = res["detail"].get("leadlag", {})

                text = (
                    f"🔍 {coin} ({hours}h)\n"
                    f"α_skor: {round(score,2)} → {sig_txt}\n"
                    f"Rejim: {round(regime,2)}\n"
                    f"Entropy: {round(entropy,2)}\n"
                    f"Kalman eğilim: {'↑' if kalman>0 else '↓'}\n"
                    f"Lead–Lag (BTC): {leadlag.get('lag',0)} bar, corr={round(leadlag.get('corr',0),2)}\n"
                )

                await context.bot.send_message(chat_id=chat_id, text=text)

        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Hata: {e}")

    asyncio.ensure_future(_run())


# ------------------------------------------------------------
# Plugin loader uyumluluk
# ------------------------------------------------------------
def register(app):
    app.add_handler(CommandHandler("t", ta_handler))
