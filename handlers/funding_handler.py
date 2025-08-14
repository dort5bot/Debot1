# handlers/funding_handler.py
# 📊 Binance Funding Rate Handler
# Plugin loader uyumlu, hem komut hem stream/polling verisi için

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Union

from utils import binance_api

LOG = logging.getLogger("funding_handler")

# Aynı anda sorgulanacak sembol sayısı
_CONCURRENCY = 12


# -------------------------------------------------
# Yardımcı Fonksiyonlar
# -------------------------------------------------
def _normalize_symbols(input_syms: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """
    input_syms: None | "btc eth" | ["btc","eth"] | ["BTCUSDT"]
    dönüş: None veya USDT ile biten büyük harfli semboller listesi
    """
    if not input_syms:
        return None
    if isinstance(input_syms, str):
        items = input_syms.split()
    else:
        items = list(input_syms)
    out = []
    for it in items:
        s = it.strip().upper()
        if not s:
            continue
        if not s.endswith("USDT"):
            s += "USDT"
        out.append(s)
    return out if out else None


async def _fetch_rate_for_symbol(sym: str, sem: asyncio.Semaphore):
    """Tek sembol için funding rate getirir."""
    async with sem:
        try:
            data = await binance_api.get_funding_rate(symbol=sym, limit=1)
            if not data:
                return None
            item = data[0] if isinstance(data, list) and data else data
            rate = float(item.get("fundingRate", 0.0)) * 100.0
            time_ms = item.get("fundingTime") or item.get("time")
            return {"symbol": sym, "rate": rate, "time_ms": time_ms}
        except Exception as e:
            LOG.debug("Fetch funding failed for %s: %s", sym, e)
            return None


# -------------------------------------------------
# Ana Rapor Fonksiyonu
# -------------------------------------------------
async def funding_report(symbols: Optional[Union[str, List[str]]] = None) -> str:
    """
    Eğer symbols None ise, tüm USDT perpetual semboller arasından mutlak değere göre
    en yüksek 10 taneyi döner. Eğer symbols verilirse sadece istenenler sorgulanır.
    """
    try:
        user_syms = _normalize_symbols(symbols)

        all_symbols = await binance_api.get_all_symbols()
        futures_symbols = [s for s in all_symbols if s.endswith("USDT")]

        if user_syms:
            futures_symbols = [s for s in user_syms if s in futures_symbols]
            if not futures_symbols:
                return "❌ Geçerli bir sembol bulunamadı."
        elif not futures_symbols:
            return "❌ Futures sembolleri alınamadı."

        sem = asyncio.Semaphore(_CONCURRENCY)
        tasks = [_fetch_rate_for_symbol(s, sem) for s in futures_symbols]
        fetched = await asyncio.gather(*tasks, return_exceptions=False)

        results = [r for r in fetched if r is not None]
        if not results:
            return "❌ Veri alınamadı."

        results.sort(key=lambda x: abs(x["rate"]), reverse=True)
        if user_syms is None:
            results = results[:10]

        avg_rate = sum(r["rate"] for r in results) / len(results)

        # Liste oluştur
        lines = []
        for r in results:
            arrow = "🔼" if r["rate"] > 0 else ("🔻" if r["rate"] < 0 else "⚪")
            ts = "-"
            if r["time_ms"]:
                try:
                    t = datetime.fromtimestamp(int(r["time_ms"]) / 1000)
                    ts = t.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            lines.append(f"{r['symbol']}: {r['rate']:.3f}% {arrow} ({ts})")

        yorum = (
            "Short yönlü baskı artıyor" if avg_rate < 0
            else "Long yönlü baskı artıyor" if avg_rate > 0
            else "Tarafsız (yakın 0)"
        )

        header = "📊 Funding Rate Raporu (Top 10)\n" if user_syms is None else "📊 Funding Rate Raporu\n"
        footer = f"\n\nGenel Ortalama: {avg_rate:.3f}% {'🔻' if avg_rate < 0 else '🔼' if avg_rate > 0 else ''}\nYorum: {yorum}"
        return header + "\n".join(lines) + footer

    except Exception as e:
        LOG.exception("funding_report hata")
        return f"❌ Funding raporu hatası: {e}"


# -------------------------------------------------
# Stream / Polling Data İşleyici
# -------------------------------------------------
async def handle_funding_data(data):
    """
    Stream veya polling ile gelen data burada işlenir.
    Beklenen formatlar:
      - WebSocket kısa format: {'s': 'BTCUSDT', 'r': '0.0001', 'T': 166...}
      - REST/polling format: {'symbol': 'BTCUSDT', 'fundingRate': '0.0001', 'fundingTime': 166...}
      - get_funding_rate() list formatı
    """
    try:
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                sym = item.get("symbol") or item.get("s")
                rate = item.get("fundingRate") or item.get("r")
                time_ms = item.get("fundingTime") or item.get("T")
                if sym and rate is not None:
                    try:
                        rate_f = float(rate) * 100.0
                        ts = datetime.fromtimestamp(int(time_ms) / 1000).strftime("%Y-%m-%d %H:%M") if time_ms else "-"
                        LOG.info("[FUNDING][POLL] %s: %.4f%% @ %s", sym, rate_f, ts)
                    except Exception:
                        LOG.debug("Malformed funding item: %s", item)
            return

        if isinstance(data, dict):
            if ("s" in data and "r" in data) or ("symbol" in data and "fundingRate" in data):
                sym = data.get("s") or data.get("symbol")
                rate = data.get("r") or data.get("fundingRate")
                time_ms = data.get("T") or data.get("fundingTime")
                try:
                    rate_f = float(rate) * 100.0
                    ts = datetime.fromtimestamp(int(time_ms) / 1000).strftime("%Y-%m-%d %H:%M") if time_ms else "-"
                    LOG.info("[FUNDING] %s: %.4f%% @ %s", sym, rate_f, ts)
                except Exception:
                    LOG.debug("Malformed funding dict: %s", data)
                return

        LOG.debug("Tanınmayan funding formatı: %s", data)

    except Exception as e:
        LOG.exception("handle_funding_data hata: %s", e)


# -------------------------------------------------
# Telegram Komutu
# -------------------------------------------------
async def _cmd_funding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram komutu: /funding veya /fr"""
    try:
        symbols = context.args if context.args else None
        text = await funding_report(symbols)
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")


# -------------------------------------------------
# Plugin Loader Entry
# -------------------------------------------------
def register(application):
    """Plugin loader uyumlu kayıt fonksiyonu"""
    application.add_handler(CommandHandler(["funding", "f","fr"], _cmd_funding))
    LOG.info("Funding handler registered.")
