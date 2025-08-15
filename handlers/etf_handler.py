# handlers/etf_handler.py
import asyncio
import logging
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.addHandler(logging.StreamHandler())

# ---------------- COINGLASS CONFIG ---------------- #
COINGLASS_BASE = os.getenv("COINGLASS_BASE", "https://open-api-v4.coinglass.com/api")
COINGLASS_KEY = os.getenv("COINGLASS_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {COINGLASS_KEY}"} if COINGLASS_KEY else {}

# ETF sağlayıcıları ve sembolleri
PROVIDER_MAP = {
    "BlackRock": ["IBIT", "ETHA"],
    "Fidelity": ["FBTC", "FETH"],
    "Grayscale": ["GBTC", "ETHE"]
}


# ---------------- UTILS ---------------- #
async def get_etf_flow_history(asset: str) -> List[Dict[str, Any]]:
    """Belirtilen varlık için ETF Net Akış geçmişini getirir."""
    if not COINGLASS_KEY:
        LOG.warning("Coinglass API key bulunamadı.")
        return []

    endpoint = f"{COINGLASS_BASE}/etf/{asset.lower()}/flow-history"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(endpoint, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            LOG.debug("[ETF] API Response for %s: %s", asset, data)
            return data.get("data", [])
    except httpx.HTTPStatusError as e:
        LOG.error("[ETF] HTTP Error %s: %s", e.response.status_code, e.response.text)
    except Exception as e:
        LOG.warning("[Coinglass] %s ETF verisi alınamadı: %s", asset, e)
    return []


async def parse_etf_report(asset: str) -> str:
    """Verilen varlık için ETF raporu hazırlar."""
    raw_data = await get_etf_flow_history(asset)
    if not raw_data:
        return f"{asset.upper()} için veri alınamadı."

    today_data = raw_data[0]
    yesterday_data = raw_data[1] if len(raw_data) > 1 else None

    total_today = sum([etf.get("flow", 0) for etf in today_data.get("etfList", [])])
    total_yesterday = sum([etf.get("flow", 0) for etf in yesterday_data.get("etfList", [])]) if yesterday_data else 0
    change = total_today - total_yesterday

    trend_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

    provider_lines = []
    for provider, tickers in PROVIDER_MAP.items():
        prov_total = sum(
            etf.get("flow", 0) for etf in today_data.get("etfList", []) if etf.get("symbol") in tickers
        )
        provider_lines.append(f"{provider}: {prov_total:,.0f} $")

    report = (
        f"📊 {asset.upper()} ETF Net Akış\n"
        f"Total: {total_today:,.0f} $ ({'+' if change>0 else ''}{change:,.0f} $) {trend_emoji}\n"
        + "\n".join(provider_lines)
    )
    return report


# ---------------- HANDLER ---------------- #
async def etf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/etf komutu ile ETF raporu gönderir."""
    if not context.args:
        await update.message.reply_text("Kullanım: /etf BTC veya /etf ETH")
        return

    asset = context.args[0].upper()
    await update.message.reply_text(f"⏳ {asset} ETF verileri alınıyor...")
    msg = await parse_etf_report(asset)
    await update.message.reply_text(msg)


def register(application):
    """Plugin loader ile uyumlu register fonksiyonu."""
    handler = CommandHandler("etf", etf_command)
    application.add_handler(handler)
