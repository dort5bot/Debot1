# handlers/io_handler.py

import asyncio
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils.binance_api import get_binance_api
from utils.io_utils import build_io_snapshot, safe_mean


# -------------------
# Ana fonksiyonlar
# -------------------

async def io_report(symbol: str | None = None):
    """
    Market genel nakit raporu veya spesifik coin için rapor hazırlar.
    """
    api = get_binance_api()

    if symbol is None:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    else:
        symbols = [symbol.upper()]

    snapshots = {}
    for sym in symbols:
        try:
            kl = await api.get_klines(sym, "1m", 200)
            ob = await api.get_order_book(sym, 100)
            trades = await api.get_recent_trades(sym, 500)
            ticker = await api.get_24h_ticker(sym)
            funding = await api.get_funding_rate(sym)

            snap = build_io_snapshot(
                sym, kl, ob, trades, ticker, funding[0] if funding else {}
            )
            snapshots[sym] = snap
        except Exception as e:
            snapshots[sym] = {"error": str(e)}

    return snapshots


def pattern_from_scores(scores: list[float]) -> str:
    """Trend pattern üretir: +, -, x"""
    out = ""
    for s in scores:
        if s is None:
            out += "x"
        elif s > 0:
            out += "+"
        else:
            out += "-"
    return out


def format_io_market(snapshots: dict) -> str:
    """Market raporu formatlar"""
    lines = ["⚡ Nakit raporu\n"]

    avg_trend = safe_mean([snap.get("trend_score") for snap in snapshots.values() if snap])
    avg_liq = safe_mean([snap.get("liquidity_score") for snap in snapshots.values() if snap])
    avg_risk = safe_mean([snap.get("risk_score") for snap in snapshots.values() if snap])

    lines.append(f"Kısa Vadeli Market Alım Gücü: {avg_trend:.2f}x")
    lines.append(f"Marketteki Hacim Payı: %{(avg_liq or 0) * 100:.1f}\n")

    lines.append("⚡ Nakit Göçü Raporu")
    for sym, snap in snapshots.items():
        if "error" in snap:
            lines.append(f"{sym}: Hata {snap['error']}")
            continue

        pattern = pattern_from_scores([
            snap["trend_score"], snap["liquidity_score"], -snap["risk_score"],
            snap["trend_score"], snap["mts_score"]
        ])
        lines.append(
            f"{sym} Nakit:%{snap['taker_ratio']:.1f} "
            f"15m:%{snap['momentum']:.1f} "
            f"Mts:{snap['mts_score']:.2f} {pattern}"
        )

    lines.append("\n⚡ Yorum")
    if avg_trend and avg_trend > 0.5:
        lines.append("Market yukarı iştahlı görünüyor ✅")
    else:
        lines.append("Piyasa riskli, dikkat! ⚠️")

    return "\n".join(lines)


# -------------------
# Telegram Handler
# -------------------

async def io_cmd(update: Update, context: CallbackContext):
    args = context.args
    symbol = args[0] if args else None

    snapshots = await io_report(symbol)
    if symbol:
        snap = snapshots.get(symbol.upper())
        if not snap or "error" in snap:
            await update.message.reply_text(f"{symbol} için veri alınamadı ❌")
            return

        pattern = pattern_from_scores([
            snap["trend_score"], snap["liquidity_score"], -snap["risk_score"],
            snap["trend_score"], snap["mts_score"]
        ])
        msg = (
            f"{symbol} Nakit:%{snap['taker_ratio']:.1f} "
            f"15m:%{snap['momentum']:.1f} "
            f"Mts:{snap['mts_score']:.2f} {pattern}"
        )
        await update.message.reply_text(msg)
    else:
        msg = format_io_market(snapshots)
        await update.message.reply_text(msg)


# -------------------
# Plugin Loader uyumlu
# -------------------

def register(app):
    """
    Plugin loader entegrasyonu
    """
    app.add_handler(
        CommandHandler("io", lambda u, c: asyncio.create_task(io_cmd(u, c)))
    )
