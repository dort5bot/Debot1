# handlers/io_handler.py

import asyncio
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from utils.binance_api import get_binance_api
from utils.io_utils import build_multi_snapshot
from utils.config import CONFIG


def trend_pattern(ratios: dict) -> str:
    pattern = []
    for tf in CONFIG.IO.CASHFLOW_TIMEFRAMES.keys():
        val = ratios.get(tf, {}).get("taker_ratio")
        pattern.append("🔼" if val and val > 0 else "🔻" if val and val < 0 else "x")
    return "".join(pattern)


async def generate_io_report(symbol: str | None = None) -> str:
    api = get_binance_api()
    symbols = [symbol.upper()] if symbol else ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

    symbols_data = {}
    for sym in symbols:
        kl = await api.get_klines(sym, "1m", limit=200)
        ob = await api.get_order_book(sym, limit=50)
        trades = await api.get_agg_trades(sym, limit=500)
        ticker = await api.get_24h_ticker(sym)
        funding = (await api.get_funding_rate(sym, limit=1))[0] if CONFIG.TA.FUNDING_RATE_ENABLED else {}
        trades_fmt = [{"qty": float(t["q"]), "price": float(t["p"]), "isBuyerMaker": t["m"], "ts": t["T"]} for t in trades]

        symbols_data[sym] = {
            "klines": kl,
            "order_book": ob,
            "trades": trades_fmt,
            "ticker": ticker,
            "funding": funding,
            "oi": None,
            "liquidations": None,
        }

    snapshots = build_multi_snapshot(symbols_data, with_cashflow=True)

    if symbol:
        snap = snapshots[symbol.upper()]
        txt = f"⚡ {symbol.upper()} IO Raporu\n"
        txt += f"Kısa Vadeli Alım Gücü: {snap['taker_ratio']:.2f}X\n"
        txt += f"Marketteki Hacim Payı: %{float(snap['vwap_taker_ratio'] or 0)*100:.1f}\n\n"
        for tf, vals in snap.get("ratios", {}).items():
            tr = vals.get("taker_ratio")
            if tr is None: continue
            direction = "🔼" if tr > 0 else "🔻"
            txt += f"{tf} => %{abs(tr*100):.1f} {direction}\n"
        txt += f"\n{symbol.upper()} Nakit: %{abs(snap['taker_ratio']*100):.1f} "
        txt += f"15m:%{abs(snap['ratios']['15m']['taker_ratio']*100):.1f} "
        txt += f"Mts:{snap['mts_score']:.2f} "
        txt += trend_pattern(snap['ratios'])
        return txt

    else:
        txt = "⚡ Market Nakit Raporu\n"
        all_ratios = [snap["taker_ratio"] for snap in snapshots.values() if snap["taker_ratio"]]
        avg_ratio = sum(all_ratios)/len(all_ratios) if all_ratios else 0
        txt += f"Kısa Vadeli Market Alım Gücü: {avg_ratio:.2f}X\n\n"
        txt += "⚡ Market 5 zamana ait nakit yüzdesi\n"
        for tf in CONFIG.IO.CASHFLOW_TIMEFRAMES.keys():
            vals = [snap["ratios"].get(tf, {}).get("taker_ratio") for snap in snapshots.values()]
            vals = [v for v in vals if v is not None]
            if not vals: continue
            avg = sum(vals)/len(vals)
            direction = "🔼" if avg > 0 else "🔻"
            txt += f"{tf} => %{abs(avg*100):.1f} {direction}\n"

        txt += "\n⚡ Coin Nakit Göçü Raporu\n"
        for sym, snap in snapshots.items():
            tr = snap['taker_ratio'] or 0
            txt += f"{sym} Nakit:%{abs(tr*100):.1f} "
            txt += f"15m:%{abs((snap['ratios']['15m']['taker_ratio'] or 0)*100):.1f} "
            txt += f"Mts:{snap['mts_score']:.2f} "
            txt += trend_pattern(snap['ratios'])
            txt += "\n"

        txt += "\n⚡ Yorum\n"
        txt += "Piyasa ciddi anlamda risk barındırıyor. Alım yapma!\n"
        return txt


def io_handler(update: Update, context: CallbackContext):
    args = context.args
    symbol = args[0] if args else None
    report = asyncio.run(generate_io_report(symbol))
    update.message.reply_text(report)


def register(app):
    app.add_handler(CommandHandler("io", io_handler))
