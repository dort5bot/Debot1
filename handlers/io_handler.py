# handlers/io_handler.py
import logging
from time import time
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils.io_utils import build_io_snapshot
from utils.binance_api import (
    get_klines,
    get_order_book,
    get_recent_trades,
    get_ticker,
    get_funding_rate,
    get_open_interest,
    get_liquidations
)

logger = logging.getLogger(__name__)

# ===============================
# --- Yardımcı Fonksiyonlar ---
# ===============================

def trend_pattern(flow_dict: dict):
    """
    Zamana göre trend oku çıkarır (+ yukarı, - aşağı, x nötr)
    """
    pattern = []
    for tf in ["15m", "1h", "4h", "12h", "1d"]:
        val = flow_dict.get(tf, 50)
        if val > 52:
            pattern.append("🔼")
        elif val < 48:
            pattern.append("🔻")
        else:
            pattern.append("➖")
    return "".join(pattern)

def calc_flow_ratio(trades, timeframe_sec: int):
    """
    Taker bazlı alış yüzdesi (buy_qty / total_qty)
    timeframe_sec: 15m=900, 1h=3600, ...
    """
    cutoff = time() * 1000 - timeframe_sec * 1000
    buys = sum(float(t["qty"]) for t in trades if not t["isBuyerMaker"] and t["time"] >= cutoff)
    sells = sum(float(t["qty"]) for t in trades if t["isBuyerMaker"] and t["time"] >= cutoff)
    total = buys + sells
    return round((buys / total) * 100, 2) if total > 0 else 50.0

def calc_multi_flows(trades):
    """
    5 zaman periyoduna göre alış yüzdeleri
    """
    return {
        "15m": calc_flow_ratio(trades, 900),
        "1h": calc_flow_ratio(trades, 3600),
        "4h": calc_flow_ratio(trades, 14400),
        "12h": calc_flow_ratio(trades, 43200),
        "1d": calc_flow_ratio(trades, 86400),
    }

# ===============================
# --- IO Handler ---
# ===============================

def io(update: Update, context: CallbackContext):
    """
    /io komutu: Nakit Göçü Raporu üretir (Binance verisi ile)
    """
    chat_id = update.effective_chat.id

    try:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        report_lines = ["⚡ Nakit Göçü Raporu\n"]

        for sym in symbols:
            try:
                # Binance API'den verileri çek
                klines = get_klines(sym, interval="5m", limit=100)
                order_book = get_order_book(sym, limit=50)
                trades = get_recent_trades(sym, limit=500)
                ticker = get_ticker(sym)
                funding = get_funding_rate(sym)
                oi = get_open_interest(sym)
                liqs = get_liquidations(sym, limit=100)

                # Snapshot analizi
                snapshot = build_io_snapshot(
                    symbol=sym,
                    klines=klines,
                    order_book=order_book,
                    trades=trades,
                    ticker=ticker,
                    funding=funding,
                    oi=oi,
                    liquidations=sum(x.get("qty", 0) for x in liqs) if liqs else 0
                )

                # Flow oranları (5 timeframe)
                flows = calc_multi_flows(trades)
                pattern = trend_pattern(flows)

                report_lines.append(
                    f"{sym.replace('USDT','')} Nakit:%{flows['1d']} "
                    f"15m:%{flows['15m']} "
                    f"Mts:{round(snapshot['mts_score'],2)} "
                    f"{pattern}"
                )

            except Exception as inner_e:
                logger.error(f"{sym} verisi alınamadı: {inner_e}")
                report_lines.append(f"{sym.replace('USDT','')} ❌ Veri alınamadı")

        # Genel yorum
        report_lines.append("\n⚡ Yorum")
        report_lines.append(
            "📊 1d değerleri %50 altında olan coinlerde risk yüksek. "
            "Alış oranı %55 üzeri olanlar güçlü alıcı baskısı taşıyor."
        )

        context.bot.send_message(chat_id=chat_id, text="\n".join(report_lines))

    except Exception as e:
        logger.error(f"IO handler error: {e}", exc_info=True)
        context.bot.send_message(chat_id=chat_id, text="⚠️ IO raporu oluşturulamadı.")

# ===============================
# --- Handler Export ---
# ===============================

def get_handler():
    """Klasik kullanım için CommandHandler döndürür"""
    return CommandHandler("io", io)

# ===============================
# --- Plugin Loader Uyumu ---
# ===============================

def register(app):
    """
    Plugin loader için handler kaydı
    app: telegram.ext.Application
    """
    app.add_handler(get_handler())
