#utils/coinglass_utils.py

import os
import logging
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

LOG = logging.getLogger("coinglass_utils")
LOG.addHandler(logging.NullHandler())

COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")
COINGLASS_BASE_URL = "https://open-api-v4.coinglass.com/api"

def _get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"CG-API-KEY": COINGLASS_API_KEY}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        LOG.error(f"Coinglass API error: {e}")
        return {}

def add_trend_arrow(current: float, previous: float) -> str:
    try:
        if previous == 0 or previous is None:
            return "➖"
        if current > previous:
            return "🔺"
        elif current < previous:
            return "🔻"
        else:
            return "➖"
    except Exception:
        return "➖"

def get_funding_rates(symbol: str = "BTC") -> Dict[str, Any]:
    url = f"{COINGLASS_BASE_URL}/futures/funding-rate/exchange-list"
    data = _get(url, params={"symbol": symbol})
    return data.get("data", {})

def get_open_interest(symbol: str = "BTC") -> Dict[str, Any]:
    url = f"{COINGLASS_BASE_URL}/futures/open-interest/exchange-history-chart"
    data = _get(url, params={"symbol": symbol})
    return data.get("data", {})

def get_exchange_balance(symbol: str = "BTC") -> Dict[str, Any]:
    url = f"{COINGLASS_BASE_URL}/exchange/balance/list"
    data = _get(url, params={"symbol": symbol})
    return data.get("data", {})

def get_top_trader_long_short(symbol: str = "BTC") -> Dict[str, Any]:
    url = f"{COINGLASS_BASE_URL}/futures/long-short-ratio/top-account-ratio-history"
    data = _get(url, params={"symbol": symbol})
    return data.get("data", {})

def get_liquidation_history(symbol: str = "BTC", interval: str = "24h") -> Dict[str, Any]:
    url = f"{COINGLASS_BASE_URL}/futures/liquidation-history"
    data = _get(url, params={"symbol": symbol, "interval": interval})
    return data.get("data", {})

def build_exchange_report(symbol: str = "BTC") -> str:
    report_lines = [f"📊 Coinglass Raporu: {symbol}"]

    funding = get_funding_rates(symbol)
    if funding:
        current = funding.get("funding_rate", 0)
        prev = funding.get("predicted_funding_rate", 0)
        arrow = add_trend_arrow(current, prev)
        report_lines.append(f"• Funding Rate: {current:.4f} ({arrow})")

    oi = get_open_interest(symbol)
    if oi:
        current = oi.get("open_interest_usd", 0)
        prev = oi.get("prev_open_interest_usd", 0)
        arrow = add_trend_arrow(current, prev)
        report_lines.append(f"• Open Interest: {current:,.0f} USD ({arrow})")

    bal = get_exchange_balance(symbol)
    if bal:
        total = bal.get("total_balance", 0)
        change = bal.get("balance_change_1d", 0)
        arrow = add_trend_arrow(total, total - change)
        report_lines.append(f"• Exchange Balance: {total:,.0f} ({arrow})")

    top = get_top_trader_long_short(symbol)
    if top:
        acct_long = top.get("long_account", 0)
        acct_short = top.get("short_account", 0)
        vol_long = top.get("long_volume", 0)
        vol_short = top.get("short_volume", 0)
        report_lines.append(
            f"• Top Trader Ratio:\n   Accounts L/S: {acct_long:.1f}% / {acct_short:.1f}%\n   Volume L/S: {vol_long:.1f}% / {vol_short:.1f}%"
        )

    liq = get_liquidation_history(symbol)
    if liq:
        long_liq = liq.get("long_vol_usd", 0)
        short_liq = liq.get("short_vol_usd", 0)
        arrow = "🔻" if long_liq > short_liq else "🔺"
        report_lines.append(
            f"• 24h Liquidations: Long={long_liq:,.0f} USD, Short={short_liq:,.0f} USD ({arrow})"
        )

    return "\n".join(report_lines)
